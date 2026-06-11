"""Demo dashboard — "cooking show".

Data sudah "dimasak" (fixtures lokal). Dashboard menjalankan step deteksi
+ tabel secara LIVE, menampilkan mekanisme per-post:
Layer 1 → Layer 2 → sinyal → confidence → keputusan, lalu metrics agregat.

Jalankan:  python -m src.demo.app
Butuh:     pip install gradio   (jika belum)
"""
from __future__ import annotations

from ..detect.layer1_deterministic import detect_layer1
from ..detect.layer2_semantic import SemanticMatcher
from ..detect.registry import BrandRegistry
from ..detect.scoring import score_candidate
from ..ingest.loader import load_from_fixtures
from ..metrics.evaluate import evaluate


def _analyze_post(post, registry, matcher):
    """Jalankan deteksi satu post, kembalikan langkah-langkah untuk ditampilkan."""
    steps = []
    l1 = detect_layer1(post, registry)
    strong = [c for c in l1 if c["signals"].get("exact_match") or c["signals"].get("official_tag")]

    used_layer = "Layer 1 (deterministik)"
    cands = strong
    if not strong:
        used_layer = "Layer 2 (semantic/fuzzy)"
        cands = matcher.detect(post)

    results = [score_candidate(post, c) for c in cands]
    return used_layer, results


def build_app():
    import gradio as gr

    posts = load_from_fixtures()
    registry = BrandRegistry.load()
    matcher = SemanticMatcher(registry)
    post_by_label = {f"{p.post_id} — {p.handle} ({p.platform})": p for p in posts}

    def run_one(label):
        post = post_by_label[label]
        used_layer, results = _analyze_post(post, registry, matcher)

        cap = f"### Caption\n> {post.caption}\n\n"
        cap += f"**Hashtags:** {', '.join(post.hashtags) or '—'}  \n"
        cap += f"**Mentions:** {', '.join(post.mentions) or '—'}  \n"
        cap += f"**Links:** {', '.join(post.links) or '—'}  \n\n"
        cap += f"**Jalur deteksi:** {used_layer}\n"

        if not results:
            return cap, [["—", "—", "tidak ada brand terdeteksi", "—", "drop"]]

        rows = []
        for d in results:
            sig = ", ".join(f"{k}:{v:+.2f}" for k, v in d.signals.items())
            rows.append([d.brand_name, d.chain, sig, f"{d.confidence:.2f}",
                         d.decision.upper()])
        return cap, rows

    def run_metrics():
        r = evaluate(review_counts_as_positive=False)
        c = r["confusion"]
        md = "### Metrics (fraud-style, accept-only)\n\n"
        md += f"- **Precision:** {r['precision']}  \n"
        md += f"- **Recall:** {r['recall']}  \n"
        md += f"- **F1:** {r['f1']}  \n"
        md += f"- **Brand accuracy (pada TP):** {r['brand_accuracy_on_tp']}  \n"
        md += f"- Support: {r['support']['positives']} pos / {r['support']['negatives']} neg\n\n"
        md += f"| | Pred POS | Pred NEG |\n|---|---|---|\n"
        md += f"| **True POS** | {c['tp']} | {c['fn']} |\n"
        md += f"| **True NEG** | {c['fp']} | {c['tn']} |\n\n"
        if r["errors"]:
            md += "**Diarahkan ke manual review / inspeksi:**\n"
            for pid, kind, info in r["errors"]:
                md += f"- `{pid}` — {kind}" + (f" (brand={info})" if info else "") + "\n"
        return md

    with gr.Blocks(title="Endorsement Detection — Demo") as app:
        gr.Markdown(
            "# Endorsement Detection — Live Demo\n"
            "Data influencer sudah dikumpulkan sebelumnya (fixtures lokal). "
            "Demo ini menjalankan **deteksi step 3–4 secara live** untuk menunjukkan "
            "cara algoritma bekerja: Layer 1 deterministik → Layer 2 semantic → "
            "confidence scoring → keputusan."
        )
        with gr.Row():
            with gr.Column(scale=1):
                dd = gr.Dropdown(list(post_by_label), label="Pilih postingan",
                                 value=list(post_by_label)[0])
                btn = gr.Button("Jalankan deteksi", variant="primary")
                meta = gr.Markdown()
            with gr.Column(scale=2):
                table = gr.Dataframe(
                    headers=["Brand", "Chain", "Sinyal (kontribusi)", "Confidence", "Keputusan"],
                    label="Hasil deteksi", wrap=True,
                )
        gr.Markdown("---")
        mbtn = gr.Button("Hitung metrics agregat")
        mout = gr.Markdown()

        btn.click(run_one, inputs=dd, outputs=[meta, table])
        mbtn.click(run_metrics, outputs=mout)

    return app


if __name__ == "__main__":
    build_app().launch()
