"""Confidence scoring & keputusan.

Menggabungkan sinyal dari kandidat (Layer 1 atau 2) menjadi skor [0,1] dan
memetakan ke keputusan accept / review / drop berdasarkan threshold di config.
Setiap kontribusi sinyal disimpan agar bisa diaudit (transparan untuk demo).
"""
from __future__ import annotations

from ..config import SCORING
from ..models import Detection, Post


def score_candidate(post: Post, candidate: dict) -> Detection:
    s = candidate["signals"]
    cfg = SCORING
    contrib: dict[str, float] = {}

    if s.get("exact_match"):
        contrib["exact_match"] = cfg.w_exact_match
    if s.get("official_tag"):
        contrib["official_tag"] = cfg.w_official_tag
    if s.get("paid_disclosure"):
        contrib["paid_disclosure"] = cfg.w_paid_disclosure
    if s.get("affiliate_link"):
        contrib["affiliate_link"] = cfg.w_affiliate_link
    if s.get("repeat_mention"):
        contrib["repeat_mention"] = cfg.w_repeat_mention
    if s.get("single_mention"):
        contrib["single_mention"] = cfg.w_single_mention
    if s.get("common_word"):
        contrib["common_word"] = cfg.w_common_word

    # Layer 2: skor semantic sebagai kontribusi dasar (di-skala)
    if candidate.get("layer") == "semantic":
        sem = s.get("semantic_score", 0.0)
        contrib["semantic_base"] = round(0.4 * sem, 4)

    raw = sum(contrib.values())
    confidence = max(0.0, min(1.0, raw))

    if confidence >= cfg.accept_threshold:
        decision = "accept"
    elif confidence >= cfg.review_low:
        decision = "review"
    else:
        decision = "drop"

    brand = candidate["brand"]
    return Detection(
        post_id=post.post_id,
        handle=post.handle,
        brand_id=brand.brand_id,
        brand_name=brand.canonical_name,
        chain=brand.chain,
        logo_url=brand.logo_url,
        confidence=confidence,
        decision=decision,
        layer=candidate.get("layer", "deterministic"),
        signals=contrib,
    )
