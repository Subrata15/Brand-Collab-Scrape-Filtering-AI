# Arsitektur — Endorsement Detection Pipeline

Dokumen ini menjelaskan **bagaimana** pipeline bekerja dan **mengapa** keputusan
desain diambil. Ditujukan untuk pembaca teknis.

## Masalah inti

Bukan "deteksi nama brand dari teks" (itu bagian yang relatif mudah). Masalah
tersulit ada dua, dan keduanya tanpa label:

1. **Endorsement vs sekadar mention.** Orang memakai sepatu Nike di foto ≠
   endorse Nike. Memuji Apple sambil bilang "ini bukan sponsored" ≠ endorsement.
2. **Brand ambigu.** Nama brand berupa kata umum (Gap, Apple, Coach), parent/child
   (Samsung/Galaxy), atau disebut tidak langsung.

## Pendekatan: 2 layer, recall-leaning, precision-filtered

### Layer 1 — Deterministik (semua post)
Cepat & presisi. Mendeteksi kandidat via:
- **Mention → official handle** brand (sinyal terkuat, paling presisi).
- **Alias/canonical name di teks** dengan *word-boundary matching* (regex) agar
  "gap" tidak salah cocok di dalam kata lain, tapi "mind the gap" tetap terdeteksi
  sebagai kandidat (lalu diturunkan skornya karena kata umum).
- Menghitung **frekuensi sebut** (occurrences) untuk sinyal repeat-mention.

Post tanpa kandidat kuat (tak ada exact/handle match) **diteruskan ke Layer 2**.

### Layer 2 — Semantic (hanya sisa, batch)
Untuk kasus implisit/typo/variasi penulisan:
- **Fuzzy matching** (rapidfuzz) lebih dulu — murah, menangkap typo.
- **Embedding multilingual** (sentence-transformers) — menangkap kemiripan makna
  lintas bahasa. Encoder dapat ditukar via `config.semantic_model`.
- *Graceful degrade*: bila model tak terpasang, jatuh ke fuzzy-only.

### Confidence scoring (gabungan sinyal)
Skor = penjumlahan kontribusi sinyal berbobot, di-clamp ke [0,1]:

| Sinyal | Arah | Rasional |
|---|---|---|
| exact_match | + | brand benar-benar disebut |
| official_tag | + | tag akun brand resmi = sinyal kolaborasi kuat |
| paid_disclosure (#ad, #sponsored, #endorse, ...) | + | penanda eksplisit |
| affiliate_link / kode diskon | + | indikator komersial |
| repeat_mention (≥2x) | + | penyebutan berulang |
| single_mention (1x, tanpa sinyal lain) | − | mungkin hanya mention organik |
| common_word (Gap/Apple/...) | − | menahan false positive kata umum |

Pemetaan keputusan:
- `confidence ≥ accept_threshold` → **accept** (masuk dataset)
- `review_low ≤ confidence < accept` → **review** (antrian validasi manual)
- `< review_low` → **drop**

Filosofi: **lebih baik false positive daripada false negative.** Endorsement nyata
yang terlewat = lubang permanen di dataset; false positive bisa disaring di antrian
review. Karena itu kami optimalkan recall, lalu presisi dipulihkan via threshold +
manual validation "where it matters" — persis sinyal cheap (post tanpa link, sebut
brand <2x) yang mengarahkan mata manusia hanya ke kasus yang perlu.

## Output
Tabel `influencer × brand`: handle, brand, chain, logo_url, confidence, decision,
layer. Lihat `src/store/db.py`.

## Skala & produksi (jujur)
- **SQLite hanya untuk POC.** Produksi 1M+ → Supabase/PostgreSQL; schema dibuat
  portabel. Penulisan di bawah beban (mereka pernah kena CPU bottleneck) ditangani
  dengan batched writes + connection pooling di produksi.
- **Biaya** (Apify, embedding inference, proxy) bersifat terukur per unit, sehingga
  bisa diproyeksikan ke 1M record untuk keperluan approval budget.
- **Scraping** idealnya pelengkap: jika tersedia API branded-content / paid-partnership
  resmi, sebagian besar endorsement sudah ter-tag di sumber — jauh lebih akurat &
  mengurangi beban/legal-risk scraping.
