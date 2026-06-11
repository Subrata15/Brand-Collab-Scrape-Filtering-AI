"""Layer 1 — deteksi deterministik (cepat, murah, precision tinggi).

Mengembalikan kandidat (post, brand) beserta sinyal yang ditemukan. Tidak
mengambil keputusan accept/drop di sini — itu tugas scoring. Layer ini juga
menandai post mana yang TIDAK menghasilkan kandidat kuat, agar bisa diteruskan
ke Layer 2 (semantic) sebagai kandidat ambigu.
"""
from __future__ import annotations

import re

from ..config import SCORING
from ..models import Post
from .registry import BrandRegistry


def _word_present(needle: str, haystack: str) -> bool:
    """Match dengan batas kata agar 'gap' tidak cocok di 'gaple'/'mind the gap'
    tetap cocok, tapi substring acak tidak. Untuk alias multi-kata, cek frasa."""
    pattern = r"(?<!\w)" + re.escape(needle) + r"(?!\w)"
    return re.search(pattern, haystack, flags=re.IGNORECASE) is not None


def _count_occurrences(needle: str, haystack: str) -> int:
    pattern = r"(?<!\w)" + re.escape(needle) + r"(?!\w)"
    return len(re.findall(pattern, haystack, flags=re.IGNORECASE))


def detect_layer1(post: Post, registry: BrandRegistry) -> list[dict]:
    """Hasil: list kandidat dict {brand, signals, layer}. Bisa kosong."""
    text = post.caption
    text_low = text.lower()
    candidates: dict[str, dict] = {}   # brand_id -> kandidat

    # 1) Match via mention ke official handle (sinyal kuat & presisi)
    for m in post.mentions:
        brand = registry.by_handle(m)
        if brand:
            c = candidates.setdefault(brand.brand_id, {"brand": brand, "signals": {}})
            c["signals"]["official_tag"] = True

    # 2) Match via alias / canonical name di teks (word-boundary)
    for alias, brand in registry.aliases().items():
        if _word_present(alias, text_low):
            c = candidates.setdefault(brand.brand_id, {"brand": brand, "signals": {}})
            occ = _count_occurrences(alias, text_low)
            c["signals"]["exact_match"] = True
            c["signals"]["occurrences"] = max(c["signals"].get("occurrences", 0), occ)
            if brand.common_word:
                c["signals"]["common_word"] = True

    # 3) Sinyal level-post (berlaku untuk semua kandidat di post ini)
    has_paid = any(mk in text_low for mk in SCORING.paid_markers) or \
        any(h.lower() in SCORING.paid_markers for h in post.hashtags) or \
        any(any(mk in h.lower() for mk in ("partner", "ambassador", "ad", "sponsor", "endorse", "kerjasama", "gifted"))
            for h in post.hashtags)
    has_link = len(post.links) > 0

    for c in candidates.values():
        c["signals"]["paid_disclosure"] = has_paid
        c["signals"]["affiliate_link"] = has_link
        occ = c["signals"].get("occurrences", 0)
        c["signals"]["repeat_mention"] = occ >= 2
        c["signals"]["single_mention"] = occ == 1 and not c["signals"].get("official_tag", False)
        c["layer"] = "deterministic"

    return list(candidates.values())
