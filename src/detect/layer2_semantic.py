"""Layer 2 — deteksi semantic (embedding multilingual + fuzzy).

Hanya dijalankan untuk post yang TIDAK menghasilkan kandidat kuat di Layer 1
(mis. brand disebut implisit / typo / variasi penulisan / lintas bahasa).
Encoder bisa ditukar lewat config.semantic_model.

Dua sub-jalur, dari murah ke mahal:
  1. Fuzzy (rapidfuzz)  — tangkap typo/varian ejaan ringan, tanpa model.
  2. Embedding multilingual — tangkap kemiripan makna lintas bahasa untuk
     varian yang lolos fuzzy. Dua keputusan desain yang membuat embedding
     benar-benar berguna untuk mention implisit (lihat docs/log_dev.md §3):
       a. Brand direpresentasikan sebagai "dokumen" (canonical + alias + chain),
          bukan hanya nama pendek — memberi permukaan makna yang cukup.
       b. Dicocokkan ke tiap KLAUSA/kalimat caption (window), ambil cosine
          maksimum — agar mention di satu klausa tidak terdilusi caption panjang.

Desain lazy: model di-load saat pertama dipakai agar import modul tidak berat
dan agar mode fixtures murni-deterministik tetap cepat. Bila model tak terpasang,
graceful degrade ke fuzzy-only (POC tetap jalan tanpa download model besar).
"""
from __future__ import annotations

import re

from ..config import SCORING
from ..models import Post
from .registry import BrandRegistry

try:
    from rapidfuzz import fuzz
except ImportError:
    fuzz = None


def _strip_sep(text: str) -> str:
    """Hilangkan separator dalam-kata (- _ . / ') agar varian penulisan brand
    seperti 'toko-pedia' / 'some.thinc' menyatu jadi 'tokopedia' / 'somethinc'."""
    return re.sub(r"[-_./']", "", text)


def _windows(caption: str) -> list[str]:
    """Pecah caption jadi klausa/kalimat (pemisah kalimat + koma + newline).

    Mention brand biasanya berada di satu klausa; mencocokkan per-window
    menghindari dilusi makna oleh sisa caption yang panjang. Caption utuh tetap
    disertakan sebagai fallback."""
    parts = re.split(r"[.!?\n]+|,", caption)
    parts = [p.strip() for p in parts if p.strip()]
    if caption.strip() and caption.strip() not in parts:
        parts.append(caption.strip())
    return parts or [caption]


def _brand_doc(brand) -> str:
    """Representasi makna brand: nama kanonik + alias + chain.

    Lebih kaya dari nama pendek sehingga embedding punya konteks cukup untuk
    mencocokkan mention implisit/lintas-bahasa."""
    parts = [brand.canonical_name, *brand.aliases]
    if brand.chain:
        parts.append(brand.chain)
    # dedup ringan dengan pertahankan urutan
    seen, out = set(), []
    for p in parts:
        k = p.lower()
        if k not in seen:
            seen.add(k)
            out.append(p)
    return " ".join(out)


class SemanticMatcher:
    def __init__(self, registry: BrandRegistry, model_name: str = SCORING.semantic_model):
        self.registry = registry
        self.model_name = model_name
        self._model = None
        self._brand_emb = None
        self._brand_list = list(registry.brands)
        # statistik ringan untuk instrumentasi biaya (Task 3)
        self.embed_calls = 0          # jumlah pemanggilan model.encode
        self.embed_texts = 0          # jumlah teks (window/brand) yang di-encode

    def _ensure_model(self) -> bool:
        """Load model jika tersedia. Return False (sekali) bila tidak ada,
        sehingga pipeline jatuh ke fuzzy-only tanpa crash."""
        if self._model is False:           # sudah dicoba & gagal
            return False
        if self._model is None:
            try:
                from sentence_transformers import SentenceTransformer
            except ImportError:
                print("[Layer2] sentence-transformers tidak terpasang — "
                      "embedding dilewati, pakai fuzzy saja. "
                      "`pip install sentence-transformers` untuk mengaktifkan.")
                self._model = False
                return False
            self._model = SentenceTransformer(self.model_name)
            docs = [_brand_doc(b) for b in self._brand_list]
            self._brand_emb = self._model.encode(docs, normalize_embeddings=True)
            self.embed_calls += 1
            self.embed_texts += len(docs)
        return True

    def detect(self, post: Post) -> list[dict]:
        """Kandidat ambigu via fuzzy + kemiripan semantic (embedding)."""
        candidates: dict[str, dict] = {}   # brand_id -> kandidat (hindari duplikat)
        paid = _post_has_paid(post)
        has_link = len(post.links) > 0

        # --- (1) Fuzzy cepat (tanpa model) — typo/varian ejaan/spacing ringan ---
        # Untuk brand bernama (identitas leksikal), fuzzy lebih tepat & presisi
        # daripada embedding. Kami cocokkan ke teks asli DAN versi ter-normalisasi
        # (separator '-_./ dihapus) agar varian seperti "toko-pedia" -> "tokopedia"
        # tertangkap secara deterministik.
        if fuzz is not None:
            text_low = post.caption.lower()
            text_norm = _strip_sep(text_low)
            for b in self._brand_list:
                if b.common_word:
                    continue
                terms = [b.canonical_name.lower(), *(b.aliases or [])]
                score = 0.0
                for t in terms:
                    score = max(score,
                                fuzz.partial_ratio(t, text_low),
                                fuzz.partial_ratio(_strip_sep(t), text_norm))
                score /= 100.0
                if score >= SCORING.semantic_fuzzy_threshold:
                    candidates[b.brand_id] = {
                        "brand": b,
                        "signals": {"semantic_score": round(score, 3), "fuzzy": True,
                                    "paid_disclosure": paid, "affiliate_link": has_link},
                        "layer": "semantic",
                    }

        # --- (2) Embedding semantic (butuh model) — kemiripan makna ---
        # Dijalankan untuk brand yang BELUM tertangkap fuzzy, sehingga embedding
        # bisa menambah brand yang terlewat (recall) tanpa menimpa hit fuzzy.
        if self._ensure_model():
            import numpy as np
            windows = _windows(post.caption)
            wemb = self._model.encode(windows, normalize_embeddings=True)
            self.embed_calls += 1
            self.embed_texts += len(windows)
            # sims[i, j] = cosine(brand_i, window_j); ambil max antar-window per brand
            sims = self._brand_emb @ wemb.T
            best = sims.max(axis=1)
            for idx, b in enumerate(self._brand_list):
                if b.brand_id in candidates:
                    continue
                if SCORING.semantic_skip_common_word and b.common_word:
                    continue
                sim = float(best[idx])
                if sim >= SCORING.semantic_threshold:
                    candidates[b.brand_id] = {
                        "brand": b,
                        "signals": {"semantic_score": round(sim, 3),
                                    "paid_disclosure": paid, "affiliate_link": has_link},
                        "layer": "semantic",
                    }

        return list(candidates.values())


def _post_has_paid(post: Post) -> bool:
    text_low = post.caption.lower()
    return any(mk in text_low for mk in SCORING.paid_markers) or \
        any(any(mk in h.lower() for mk in ("partner", "ambassador", "ad", "sponsor",
                                           "endorse", "kerjasama", "gifted"))
            for h in post.hashtags)
