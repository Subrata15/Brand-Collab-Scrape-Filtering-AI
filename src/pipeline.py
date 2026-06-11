"""Orkestrasi end-to-end: ingest -> detect -> store.

Contoh:
    python -m src.pipeline --source fixtures
    python -m src.pipeline --source apify --handles data/handles.txt
    python -m src.pipeline --source fixtures --no-semantic
"""
from __future__ import annotations

import argparse
from pathlib import Path

from .detect.pipeline import run_detection
from .detect.registry import BrandRegistry
from .ingest.loader import load_posts
from .store.db import write_detections, influencer_brand_table


def main():
    ap = argparse.ArgumentParser(description="Endorsement detection POC")
    ap.add_argument("--source", choices=["fixtures", "apify"], default="fixtures")
    ap.add_argument("--handles", type=str, help="file berisi handle (mode apify)")
    ap.add_argument("--no-semantic", action="store_true", help="lewati Layer 2")
    args = ap.parse_args()

    handles = None
    if args.source == "apify":
        if not args.handles:
            ap.error("--handles wajib untuk mode apify")
        handles = [l.strip() for l in Path(args.handles).read_text().splitlines() if l.strip()]

    print(f"[1/4] Ingest ({args.source}) ...")
    posts = load_posts(args.source, handles)
    print(f"      {len(posts)} post dimuat.")

    print("[2/4] Memuat brand registry ...")
    registry = BrandRegistry.load()
    print(f"      {len(registry)} brand.")

    print("[3/4] Deteksi (Layer 1 -> Layer 2) ...")
    detections = run_detection(posts, registry, use_semantic=not args.no_semantic)
    by_decision = {}
    for d in detections:
        by_decision[d.decision] = by_decision.get(d.decision, 0) + 1
    print(f"      {len(detections)} kandidat. Keputusan: {by_decision}")

    print("[4/4] Menulis ke SQLite ...")
    n = write_detections(detections)
    print(f"      {n} baris ditulis.")

    print("\n=== Tabel influencer x brand (accepted) ===")
    for row in influencer_brand_table(only_accepted=True):
        print(f"  {row['handle']:<22} -> {row['brand_name']:<18} "
              f"(conf={row['confidence']:.2f}, {row['chain']})")


if __name__ == "__main__":
    main()
