"""Ingest layer dengan mode dual.

- `fixtures`: baca post dari JSON lokal (gratis, deterministik, untuk dev/demo).
- `apify`:    panggil Apify actor (live, butuh APIFY_TOKEN).

Keduanya mengembalikan list[Post] yang identik bentuknya, sehingga sisa
pipeline tidak peduli dari mana data berasal (decoupled scrape <-> detect).
"""
from __future__ import annotations

import json
import os
from pathlib import Path

from ..config import FIXTURES_POSTS, INGEST
from ..models import Post


def load_from_fixtures(path: Path = FIXTURES_POSTS) -> list[Post]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return [Post.from_dict(p) for p in data["posts"]]


def load_from_apify(handles: list[str]) -> list[Post]:
    """Scrape live via Apify. Dipanggil hanya saat --source apify.

    Catatan: actor IG/TikTok mengembalikan skema berbeda; fungsi _normalize_*
    memetakannya ke Post. Skema bisa berubah saat platform update — ini titik
    maintenance yang sengaja diisolasi di sini.
    """
    try:
        from apify_client import ApifyClient
    except ImportError as e:
        raise RuntimeError(
            "apify-client belum terpasang. `pip install apify-client` "
            "atau gunakan --source fixtures."
        ) from e

    token = os.getenv("APIFY_TOKEN")
    if not token:
        raise RuntimeError("APIFY_TOKEN tidak ditemukan di environment (.env).")

    client = ApifyClient(token)
    posts: list[Post] = []

    ig_handles = [h for h in handles if not h.startswith("tt:")]
    tt_handles = [h.removeprefix("tt:") for h in handles if h.startswith("tt:")]

    if ig_handles:
        run = client.actor(INGEST.apify_ig_actor).call(run_input={
            "directUrls": [f"https://instagram.com/{h.lstrip('@')}" for h in ig_handles],
            "resultsLimit": INGEST.max_posts_per_handle,
        })
        for item in client.dataset(run["defaultDatasetId"]).iterate_items():
            posts.append(_normalize_ig(item))

    if tt_handles:
        run = client.actor(INGEST.apify_tt_actor).call(run_input={
            "profiles": tt_handles,
            "resultsPerPage": INGEST.max_posts_per_handle,
        })
        for item in client.dataset(run["defaultDatasetId"]).iterate_items():
            posts.append(_normalize_tt(item))

    return posts


def _normalize_ig(item: dict) -> Post:
    caption = item.get("caption") or ""
    return Post(
        post_id=str(item.get("id", item.get("shortCode", ""))),
        handle="@" + str(item.get("ownerUsername", "")),
        platform="instagram",
        caption=caption,
        hashtags=_extract_hashtags(caption),
        mentions=["@" + m for m in item.get("mentions", [])],
        links=[u for u in [item.get("url")] if u],
    )


def _normalize_tt(item: dict) -> Post:
    caption = item.get("text") or ""
    author = item.get("authorMeta", {}).get("name", "")
    return Post(
        post_id=str(item.get("id", "")),
        handle="@" + str(author),
        platform="tiktok",
        caption=caption,
        hashtags=_extract_hashtags(caption),
        mentions=[],
        links=[u for u in [item.get("webVideoUrl")] if u],
    )


def _extract_hashtags(text: str) -> list[str]:
    return [w.lower() for w in text.split() if w.startswith("#")]


def load_posts(source: str, handles: list[str] | None = None) -> list[Post]:
    if source == "fixtures":
        return load_from_fixtures()
    if source == "apify":
        if not handles:
            raise ValueError("Mode apify butuh daftar handles.")
        return load_from_apify(handles)
    raise ValueError(f"Sumber tidak dikenal: {source!r}")
