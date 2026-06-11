# Brand Collaboration Detection

Pipeline untuk mendeteksi **brand endorsement / paid collaboration** dari
postingan influencer (TikTok & Instagram) dan menghasilkannya sebagai tabel
enrichment **influencer × brand** — brand yang di-endorse beserta nama/chain,
link/logo, dan skor kepercayaan (confidence).

Tantangan intinya bukan sekadar menemukan nama brand di dalam teks, melainkan
membedakan **endorsement nyata** dari mention organik (memakai sepatu Nike di
foto ≠ meng-endorse Nike; memuji produk sambil bilang "ini bukan sponsored" ≠
endorsement), sekaligus menyelesaikan nama yang ambigu (kata umum seperti
*Gap*/*Apple*, relasi parent/child seperti *Samsung*/*Galaxy*, atau sebutan tak
langsung) — lintas bahasa dan tanpa label.

## Pendekatan

Deteksi **dua lapis**, dengan prinsip **recall-leaning, precision-filtered**:
tangkap kandidat seluas mungkin, lalu pulihkan presisi melalui ambang
confidence dan antrian review manual. Alasannya, satu endorsement nyata yang
terlewat menjadi lubang permanen di dataset, sementara false positive masih bisa
disaring belakangan.

```
  Ingest (Apify / fixtures)
        │   raw posts: caption, hashtags, mentions, links
        ▼
  Layer 1 — Deterministik  (cepat, presisi tinggi, untuk semua post)
        │   exact/alias word-boundary match · @handle → brand · sinyal #ad/link
        │   → hit kuat            ➜ langsung di-scoring
        │   → kandidat ambigu     ➜ diteruskan ke Layer 2
        ▼
  Layer 2 — Semantic  (hanya sisa post)
        │   fuzzy (typo/spacing, ter-normalisasi) → embedding multilingual
        ▼
  Confidence scoring  (penjumlahan sinyal berbobot, clamp [0,1])
        │   ≥ 0.60  ➜ accept   ·   0.30–0.60  ➜ review   ·   < 0.30  ➜ drop
        ▼
  Output: tabel influencer × brand
```

Penjelasan keputusan desain selengkapnya ada di [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).

## Instalasi

```bash
python -m venv .venv && source .venv/bin/activate    # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## Menjalankan

```bash
# Jalankan pipeline penuh dari fixtures lokal (gratis, tanpa Apify)
python -m src.pipeline --source fixtures

# Jalankan dari Apify (live; butuh APIFY_TOKEN di .env)
python -m src.pipeline --source apify --handles data/handles.txt

# Hitung metrics terhadap labeled fixtures
python -m src.metrics.evaluate

# Jalankan test
python -m pytest tests/ -q
```

## Mode sumber data

| Mode       | Sumber                      | Biaya  | Kapan dipakai           |
|------------|-----------------------------|--------|-------------------------|
| `fixtures` | JSON tersimpan di `data/`   | Gratis | Pengembangan, test, demo|
| `apify`    | Apify actor (live scrape)   | Bayar  | Pengumpulan data nyata  |

Mode ingest dipisah dari deteksi (decoupled), sehingga sumber data bisa ditukar
tanpa menyentuh logika deteksi.

## Struktur proyek

```
src/
  ingest/      # Apify client + fixture loader (mode dual)
  detect/      # Layer 1 deterministik, Layer 2 semantic, confidence scoring
  store/       # SQLite schema + writer
  metrics/     # evaluasi gaya fraud-detection
  demo/        # dashboard demo
  pipeline.py  # orkestrasi end-to-end
data/
  brands/      # brand DB contoh (dummy)
  fixtures/    # post contoh + labeled ground truth
docs/
  ARCHITECTURE.md
```

## Catatan desain & batasan

Proyek ini sengaja transparan soal apa yang sudah/ belum production-ready:

- **SQLite hanya untuk POC.** SQLite dipilih agar POC ringan dan mudah dijalankan,
  tetapi tidak cocok untuk concurrent write skala besar. Target produksi adalah
  PostgreSQL/Supabase; schema dibuat portabel agar migrasinya mulus.
- **Brand DB di repo ini adalah dummy** (sejumlah kecil brand dengan edge case
  yang sengaja disisipkan). Tujuannya agar pipeline bisa dijalankan tanpa data
  sensitif; path-nya dapat diarahkan ke database brand yang sebenarnya.
- **Layer 2 memakai embedding multilingual** sebagai *back-stop* semantik. Untuk
  brand yang identitasnya leksikal (nama diri), varian ejaan/penulisan justru
  paling andal dipulihkan oleh fuzzy ter-normalisasi; embedding dipakai konservatif
  dan tidak di-*over-claim*.
- **Metrik bergaya fraud-detection.** Kelas positif (endorsement) adalah minoritas,
  sehingga evaluasi memakai precision/recall/F1/confusion matrix, bukan akurasi.
</content>
