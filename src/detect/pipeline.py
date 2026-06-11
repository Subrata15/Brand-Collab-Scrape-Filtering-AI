"""Orkestrator deteksi: jalankan Layer 1 dulu, Layer 2 untuk post tanpa
kandidat kuat, lalu scoring. Inilah implementasi 'deterministik dulu, sisanya
encoding batch'."""
from __future__ import annotations

from ..models import Detection, Post
from .layer1_deterministic import detect_layer1
from .layer2_semantic import SemanticMatcher
from .registry import BrandRegistry
from .scoring import score_candidate


def run_detection(
    posts: list[Post],
    registry: BrandRegistry,
    use_semantic: bool = True,
) -> list[Detection]:
    detections: list[Detection] = []
    semantic_queue: list[Post] = []

    # --- Layer 1: deterministik (semua post) ---
    for post in posts:
        cands = detect_layer1(post, registry)
        strong = [c for c in cands if c["signals"].get("exact_match") or c["signals"].get("official_tag")]
        if strong:
            for c in strong:
                detections.append(score_candidate(post, c))
        else:
            # tidak ada kandidat kuat -> teruskan ke Layer 2 (ambigu)
            semantic_queue.append(post)

    # --- Layer 2: semantic (batch, hanya sisa) ---
    if use_semantic and semantic_queue:
        matcher = SemanticMatcher(registry)
        for post in semantic_queue:
            for c in matcher.detect(post):
                detections.append(score_candidate(post, c))

    return detections
