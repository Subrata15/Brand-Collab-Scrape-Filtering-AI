"""SQLite store untuk POC.

CATATAN PRODUKSI: SQLite dipilih untuk POC (ringan, file-based, mudah di-share).
Untuk produksi 1M+ dengan concurrent write, ganti ke Supabase/PostgreSQL —
schema di bawah dirancang agar portabel (tipe & nama kolom netzral).
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

from ..config import DB_PATH
from ..models import Detection

SCHEMA = """
CREATE TABLE IF NOT EXISTS endorsements (
    post_id     TEXT NOT NULL,
    handle      TEXT NOT NULL,
    brand_id    TEXT NOT NULL,
    brand_name  TEXT NOT NULL,
    chain       TEXT,
    logo_url    TEXT,
    confidence  REAL NOT NULL,
    decision    TEXT NOT NULL,
    layer       TEXT NOT NULL,
    PRIMARY KEY (post_id, brand_id)
);
CREATE INDEX IF NOT EXISTS idx_handle ON endorsements(handle);
CREATE INDEX IF NOT EXISTS idx_brand  ON endorsements(brand_id);
CREATE INDEX IF NOT EXISTS idx_decision ON endorsements(decision);
"""


def init_db(path: Path = DB_PATH) -> sqlite3.Connection:
    conn = sqlite3.connect(str(path))
    conn.executescript(SCHEMA)
    conn.commit()
    return conn


def write_detections(detections: list[Detection], path: Path = DB_PATH) -> int:
    conn = init_db(path)
    rows = [
        (d.post_id, d.handle, d.brand_id, d.brand_name, d.chain,
         d.logo_url, d.confidence, d.decision, d.layer)
        for d in detections
    ]
    conn.executemany(
        """INSERT OR REPLACE INTO endorsements
           (post_id, handle, brand_id, brand_name, chain, logo_url,
            confidence, decision, layer)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        rows,
    )
    conn.commit()
    n = conn.total_changes
    conn.close()
    return len(rows)


def influencer_brand_table(path: Path = DB_PATH, only_accepted: bool = True) -> list[dict]:
    """Tabel akhir: influencer x brand yang di-endorse."""
    conn = init_db(path)
    q = """SELECT handle, brand_name, chain, logo_url, confidence, decision
           FROM endorsements"""
    if only_accepted:
        q += " WHERE decision = 'accept'"
    q += " ORDER BY handle, confidence DESC"
    rows = [dict(zip([c[0] for c in cur.description], r))
            for cur in [conn.execute(q)] for r in cur.fetchall()]
    conn.close()
    return rows
