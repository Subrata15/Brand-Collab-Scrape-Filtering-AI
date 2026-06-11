# Endorsement Detection POC — Influencer × Brand Enrichment

Proof-of-concept untuk mendeteksi **brand endorsement / collaboration** dari postingan
influencer (TikTok + Instagram) dan menghasilkan tabel enrichment:
`influencer × brand yang di-endorse + nama brand/chain + link/logo`.

POC ini membuktikan **bagian tersulit** dari proyek: mengubah caption mentah menjadi
`(brand, endorsement-confidence)` yang masuk akal — bukan sekadar menulis ke database.

---

## Arsitektur (2-layer detection)

```
  Ingest (Apify / fixtures)
        │   raw posts (caption, hashtags, mentions, links)
        ▼
  Layer 1 — DETERMINISTIK  (cepat, murah, precision tinggi)
        │   exact + alias match ke brand DB, hashtag/mention/link rules
        │   → high-confidence hits  ➜ langsung accept
        │   → sisa post yang "berpotensi tapi tak pasti"  ➜ diteruskan
        ▼
  Layer 2 — SEMANTIC  (embedding multilingual + fuzzy)
        │   hanya untuk post yang lolos Layer 1 sebagai kandidat ambigu
        │   → score kemiripan ke brand DB
        ▼
  Confidence scoring  (gabungan sinyal: link, frekuensi sebut, #ad, tag resmi)
        │   ≥ accept_threshold      ➜ auto-accept
        │   review_band             ➜ manual validation queue
        │   < drop_threshold        ➜ drop
        ▼
  Output: tabel influencer × brand  (SQLite)
```

Detail desain ada di `docs/ARCHITECTURE.md`. Catatan pengembangan berjalan di
`docs/log_dev.md`.

---

## Kejujuran teknis (penting — dibaca STARRY)

- **SQLite di POC, PostgreSQL/Supabase di produksi.** SQLite dipilih agar POC ringan,
  file-based, dan mudah di-share. SQLite **tidak** cocok untuk concurrent write skala
  1M+; produksi tetap mengikuti permintaan: Supabase/PostgreSQL.
- **Brand DB di repo ini adalah dummy** (~ratusan brand dengan edge case), bukan
  database 30k brand asli. Tujuannya agar pipeline bisa jalan tanpa data sensitif.
- **Layer 2 menggunakan embedding multilingual**, bukan model evidence-extractor
  English-only. Konten influencer global (mis. Bahasa Indonesia) butuh model multilingual.
- **Recall-leaning, precision-filtered.** Pada deteksi kami condong menangkap lebih banyak
  kandidat (lebih baik false-positive yang bisa difilter daripada kehilangan kolaborasi
  nyata), lalu menyaring dengan confidence threshold + manual queue.
- **Metrics bergaya fraud detection.** Kelas tidak seimbang (endorsement = minoritas,
  asumsi ≤15% post/akun), jadi kami pakai precision / recall / F1 / PR-curve / confusion
  matrix — bukan akurasi.

---

## Setup

```bash
python -m venv .venv && source .venv/bin/activate    # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## Menjalankan

```bash
# 1) Jalankan pipeline penuh dari fixtures lokal (gratis, tanpa Apify)
python -m src.pipeline --source fixtures

# 2) Jalankan dari Apify (live; butuh APIFY_TOKEN di .env)
python -m src.pipeline --source apify --handles data/handles.txt

# 3) Hitung metrics terhadap labeled fixtures
python -m src.metrics.evaluate

# 4) Demo dashboard ("cooking show" — jalankan step 3-4 live dari data lokal)
python -m src.demo.app
```

## Mode sumber data

| Mode       | Sumber                         | Biaya | Kapan dipakai            |
|------------|--------------------------------|-------|--------------------------|
| `fixtures` | JSON tersimpan di `data/`      | Gratis| Dev, test, demo          |
| `apify`    | Apify actor (live scrape)      | Bayar | Pengumpulan data nyata   |

## Struktur

```
src/
  ingest/      # Apify client + fixture loader (mode dual)
  detect/      # Layer 1 deterministik, Layer 2 semantic, confidence scoring
  store/       # SQLite schema + writer
  metrics/     # evaluasi gaya fraud-detection
  demo/        # dashboard "cooking show"
  pipeline.py  # orkestrasi end-to-end
data/
  brands/      # dummy brand DB
  fixtures/    # post tersimpan + labeled ground truth
docs/
  ARCHITECTURE.md
  log_dev.md   # log pengembangan section-by-section
```
