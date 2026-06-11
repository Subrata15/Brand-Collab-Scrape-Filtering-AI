"""Tipe data bersama lintas modul (dataclasses, tanpa dependency berat)."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Post:
    post_id: str
    handle: str
    platform: str
    caption: str
    hashtags: list[str] = field(default_factory=list)
    mentions: list[str] = field(default_factory=list)
    links: list[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, d: dict) -> "Post":
        return cls(
            post_id=d["post_id"],
            handle=d["handle"],
            platform=d.get("platform", "unknown"),
            caption=d.get("caption", ""),
            hashtags=d.get("hashtags", []),
            mentions=d.get("mentions", []),
            links=d.get("links", []),
        )


@dataclass
class Brand:
    brand_id: str
    canonical_name: str
    chain: str
    aliases: list[str]
    official_handles: list[str]
    logo_url: str
    common_word: bool = False

    @classmethod
    def from_dict(cls, d: dict) -> "Brand":
        return cls(
            brand_id=d["brand_id"],
            canonical_name=d["canonical_name"],
            chain=d.get("chain", ""),
            aliases=[a.lower() for a in d.get("aliases", [])],
            official_handles=[h.lower() for h in d.get("official_handles", [])],
            logo_url=d.get("logo_url", ""),
            common_word=d.get("common_word", False),
        )


@dataclass
class Detection:
    """Hasil deteksi satu (post, brand) beserta jejak sinyal untuk audit."""

    post_id: str
    handle: str
    brand_id: str
    brand_name: str
    chain: str
    logo_url: str
    confidence: float
    decision: str            # "accept" | "review" | "drop"
    layer: str               # "deterministic" | "semantic"
    signals: dict = field(default_factory=dict)   # jejak sinyal -> kontribusi

    def to_row(self) -> dict:
        return {
            "post_id": self.post_id,
            "handle": self.handle,
            "brand_id": self.brand_id,
            "brand_name": self.brand_name,
            "chain": self.chain,
            "logo_url": self.logo_url,
            "confidence": round(self.confidence, 4),
            "decision": self.decision,
            "layer": self.layer,
        }
