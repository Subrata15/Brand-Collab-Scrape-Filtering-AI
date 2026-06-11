"""Registry brand: memuat brand DB dan menyediakan lookup cepat."""
from __future__ import annotations

import json
from pathlib import Path

from ..config import BRANDS_PATH
from ..models import Brand


class BrandRegistry:
    def __init__(self, brands: list[Brand]):
        self.brands = brands
        # index alias -> brand (lowercase), dan handle -> brand
        self._alias_index: dict[str, Brand] = {}
        self._handle_index: dict[str, Brand] = {}
        for b in brands:
            for alias in b.aliases:
                self._alias_index[alias] = b
            self._alias_index[b.canonical_name.lower()] = b
            for h in b.official_handles:
                self._handle_index[h] = b

    @classmethod
    def load(cls, path: Path = BRANDS_PATH) -> "BrandRegistry":
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        return cls([Brand.from_dict(b) for b in data["brands"]])

    def by_handle(self, handle: str) -> Brand | None:
        return self._handle_index.get(handle.lower())

    def aliases(self) -> dict[str, Brand]:
        return self._alias_index

    def __len__(self) -> int:
        return len(self.brands)
