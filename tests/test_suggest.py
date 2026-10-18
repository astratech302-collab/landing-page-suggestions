import json
from pathlib import Path

import suggest as s

PAGE = {"normalized_key": "https://example.com/sale", "ad_count": 1,
        "ads": [{"headlines": ["Big Sale"], "descriptions": ["d"], "campaign": {"name": "C"},
                 "keywords": [{"text": "shirts", "match_type": "PHRASE"}]}]}


def test_norm_url():
    assert s.norm_url("HTTPS://Example.com/Sale/?a=1#x") == "https://example.com/Sale"


def test_match_by_front_matter_and_slug(tmp_path):
    (tmp_path / "a.md").write_text("---\nurl: https://EXAMPLE.com/sale/\n---\nfm")
    (tmp_path / "shirts.md").write_text("by slug")
    (tmp_path / "example-com-other.md").write_text("by host slug")
    c = s.load_clarity(tmp_path)
    assert s.find_clarity(c, "https://example.com/sale?utm=1") .endswith("fm")
    assert s.find_clarity(c, "https://example.com/shirts") == "by slug"
    assert s.find_clarity(c, "https://example.com/other") == "by host slug"
    assert s.find_clarity(c, "https://example.com/nope") is None


def test_home_slug():
    assert "home" in s.page_slugs("https://example.com/")


def test_missing_and_empty_inputs():
    p = s.build_prompt(PAGE, None, "")
    assert s.MISSING in p and s.EMPTY in p
    assert "Big Sale" in p and "shirts [PHRASE]" in p


def test_brand_and_clarity_included():
    p = s.build_prompt(PAGE, "rage clicks", "no cheap")
    assert "rage clicks" in p and "no cheap" in p and "MISSING" not in p


def test_run_dry_and_mock(tmp_path):
    rep = tmp_path / "r.json"
    rep.write_text(json.dumps({"landing_pages": [PAGE]}))
    out = tmp_path / "out"
    [f] = s.run(rep, None, None, out, dry_run=True)
    assert f.name.endswith(".prompt.md") and "MISSING" in f.read_text()
    [f] = s.run(rep, None, None, out, mock=True)
    assert f.read_text().startswith("# Suggestions:")


def test_sample_report_if_present():
    sample = Path.home() / "google-ads-integration/examples/sample-report.json"
    if sample.exists():
        assert len(s.run(sample, None, None, Path("/tmp/lps-test"), dry_run=True)) == 3
