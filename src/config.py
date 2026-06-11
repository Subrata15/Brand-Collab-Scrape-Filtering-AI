"""Konfigurasi terpusat untuk pipeline POC.

Semua angka threshold & bobot sinyal dikumpulkan di sini agar mudah di-tune
dan agar `log_dev.md` bisa mencatat perubahan parameter di satu tempat.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
BRANDS_PATH = DATA / "brands" / "brands_sample.json"
FIXTURES_POSTS = DATA / "fixtures" / "posts_sample.json"
FIXTURES_LABELS = DATA / "fixtures" / "labels_sample.json"
DB_PATH = ROOT / "endorsement_poc.sqlite"


@dataclass(frozen=True)
class ScoringConfig:
    """Bobot sinyal & threshold untuk confidence scoring.

    Confidence akhir = penjumlahan kontribusi sinyal, di-clamp ke [0, 1].
    Recall-leaning: base match sudah memberi sinyal positif kuat; sinyal
    "endorsement nyata" (link, #ad, tag resmi, repetisi) menaikkan; sinyal
    "kemungkinan hanya mention" (sekali sebut, kata umum) menurunkan.
    """

    # Kontribusi positif
    w_exact_match: float = 0.45          # brand cocok persis / alias di teks
    w_official_tag: float = 0.25         # tag/mention akun brand resmi
    w_paid_disclosure: float = 0.30      # #ad #sponsored #paidpartnership #endorse
    w_affiliate_link: float = 0.25       # ada link afiliasi / kode diskon
    w_repeat_mention: float = 0.15       # brand disebut >= 2x

    # Kontribusi negatif (menahan false positive)
    w_single_mention: float = -0.10      # brand hanya muncul 1x, tanpa sinyal lain
    w_common_word: float = -0.15         # nama brand == kata umum (Gap, Apple, dst)

    # Pita keputusan
    accept_threshold: float = 0.60       # >= -> auto-accept
    review_low: float = 0.30             # [review_low, accept) -> manual queue
    # < review_low -> drop

    # Layer 2 semantic
    # cosine minimum (caption-window vs brand-doc) agar jadi kandidat embedding.
    # Dikalibrasi pada fixtures implisit: 0.50 menangkap varian ejaan/transliterasi
    # lintas-bahasa tanpa memicu false positive pada kalimat organik (lihat log_dev).
    semantic_threshold: float = 0.50
    # ambang fuzzy (rapidfuzz) di Layer 2 — varian/typo ringan ditangkap di sini.
    semantic_fuzzy_threshold: float = 0.90
    # brand "kata umum" (Apple/Gap/Coach) dilewati di jalur embedding agar tidak
    # salah cocok dengan kalimat generik (precision guard, konsisten dgn fuzzy).
    semantic_skip_common_word: bool = True
    semantic_model: str = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"

    # Daftar disclosure & kata umum (bisa diperluas dari data)
    paid_markers: tuple[str, ...] = (
        "#ad", "#sponsored", "#paidpartnership", "#endorse", "#kerjasama",
        "#paid", "#partner", "#ambassador", "#gifted",
    )


@dataclass(frozen=True)
class IngestConfig:
    max_posts_per_handle: int = 200
    apify_ig_actor: str = "apify/instagram-scraper"
    apify_tt_actor: str = "clockworks/tiktok-scraper"


SCORING = ScoringConfig()
INGEST = IngestConfig()
