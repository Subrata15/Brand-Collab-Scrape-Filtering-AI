"""Test deteksi: verifikasi edge case kunci tidak regресi."""
from src.detect.layer1_deterministic import detect_layer1
from src.detect.registry import BrandRegistry
from src.detect.scoring import score_candidate
from src.ingest.loader import load_from_fixtures


def _detections_for(post_id):
    posts = {p.post_id: p for p in load_from_fixtures()}
    reg = BrandRegistry.load()
    post = posts[post_id]
    return [score_candidate(post, c) for c in detect_layer1(post, reg)]


def test_clear_endorsement_accepted():
    # P001: Nike + #ad + link + kode diskon -> accept dengan conf tinggi
    dets = _detections_for("P001")
    nike = [d for d in dets if d.brand_id == "B001"]
    assert nike and nike[0].decision == "accept"
    assert nike[0].confidence >= 0.6


def test_common_word_not_false_triggered():
    # P007: "mind the gap" -> Gap (kata umum) tidak boleh jadi accept
    dets = _detections_for("P007")
    accepts = [d for d in dets if d.decision == "accept"]
    assert not accepts, f"kata umum salah terdeteksi: {accepts}"


def test_explicit_not_sponsored_not_accepted():
    # P006: "Apple ... bukan sponsored" -> tidak accept
    dets = _detections_for("P006")
    accepts = [d for d in dets if d.decision == "accept"]
    assert not accepts


def test_owned_not_collab_not_accepted():
    # P011: punya tas Coach tapi bukan kolaborasi -> tidak accept
    dets = _detections_for("P011")
    accepts = [d for d in dets if d.decision == "accept"]
    assert not accepts


def test_word_boundary():
    from src.detect.layer1_deterministic import _word_present
    assert _word_present("gap", "mind the gap today")
    assert not _word_present("gap", "gaple game")


# --- Layer 2 (semantic) — fuzzy + normalisasi, dipaksa fuzzy-only agar tes
#     cepat & tidak butuh download model embedding. ---

def _layer2_fuzzy_only(post_id):
    from src.detect.layer2_semantic import SemanticMatcher
    posts = {p.post_id: p for p in load_from_fixtures()}
    reg = BrandRegistry.load()
    m = SemanticMatcher(reg)
    m._model = False  # paksa lewati embedding -> uji jalur fuzzy deterministik
    post = posts[post_id]
    return [score_candidate(post, c) for c in m.detect(post)]


def test_strip_sep_normalizes_separators():
    from src.detect.layer2_semantic import _strip_sep
    assert _strip_sep("toko-pedia") == "tokopedia"
    assert _strip_sep("some.thinc") == "somethinc"


def test_layer2_catches_separator_variant():
    # P013: "toko-pedia" (varian spacing) -> Tokopedia via fuzzy-normalisasi.
    # Dengan #ad + link harus naik ke accept (recall terjaga untuk mention implisit).
    dets = _layer2_fuzzy_only("P013")
    toped = [d for d in dets if d.brand_id == "B009"]
    assert toped and toped[0].decision == "accept", dets


def test_layer2_implicit_organic_not_accepted():
    # P015: "Samthing" tanpa sinyal berbayar/link -> tidak boleh accept (precision).
    dets = _layer2_fuzzy_only("P015")
    assert not [d for d in dets if d.decision == "accept"], dets


def test_layer2_generic_post_no_false_brand():
    # P017: post resep generik tanpa brand -> tidak boleh memunculkan accept.
    dets = _layer2_fuzzy_only("P017")
    assert not [d for d in dets if d.decision == "accept"], dets
