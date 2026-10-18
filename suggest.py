"""Per-landing-page conversion suggestions from ads report + Clarity .md + brand guidelines."""
import argparse
import json
import re
import sys
from pathlib import Path
from urllib.parse import urlsplit

MODEL = "claude-opus-5-5"
MISSING = "(MISSING: no data provided for this input. Do not infer or invent it.)"
EMPTY = "(EMPTY: file exists but has no content. Do not infer or invent it.)"

SYSTEM = (
    "You are a conversion-rate and paid-search landing-page analyst. You get Google Ads "
    "configuration (no performance metrics), optional Microsoft Clarity behavior notes, and "
    "optional brand guidelines for ONE landing page. Use only what is provided. If an input is "
    "marked MISSING or EMPTY, say so explicitly in that section and do not invent data. "
    "Write Markdown with exactly these sections: "
    "## Ad copy / landing page message match, ## Brand guideline conflicts, "
    "## Clarity behavior issues, ## Prioritized suggestions. "
    "Never claim you saw the page itself; you only see the inputs."
)


def norm_url(url: str) -> str:
    """Match key: lowercase scheme+host, path without trailing slash, no query/fragment."""
    u = urlsplit(url.strip())
    return f"{u.scheme.lower()}://{u.netloc.lower()}{u.path.rstrip('/')}"


def slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-") or "home"


def page_slugs(url: str) -> set[str]:
    """Filenames (stem) that match a page: host+path slug or path-only slug."""
    u = urlsplit(norm_url(url))
    return {slug(u.netloc + u.path), slug(u.path)}


def _front_matter_url(text: str) -> str | None:
    m = re.match(r"---\s*\n(.*?)\n---\s*(\n|$)", text, re.S)
    if m and (u := re.search(r"^url:\s*(\S+)", m.group(1), re.M)):
        return u.group(1).strip("\"'")
    return None


def load_clarity(folder: Path | None) -> dict[str, str]:
    """Map norm_url -> content, or 'slug:<stem>' -> content for files without front-matter url."""
    out: dict[str, str] = {}
    if folder and folder.is_dir():
        for f in sorted(folder.glob("*.md")):
            text = f.read_text(encoding="utf-8")
            url = _front_matter_url(text)
            out[norm_url(url) if url else "slug:" + f.stem.lower()] = text
    return out


def find_clarity(clarity: dict[str, str], page_url: str) -> str | None:
    if (t := clarity.get(norm_url(page_url))) is not None:
        return t
    for s in page_slugs(page_url):
        if (t := clarity.get("slug:" + s)) is not None:
            return t
    return None


def _section(text: str | None) -> str:
    if text is None:
        return MISSING
    return text.strip() or EMPTY


def ad_summary(ad: dict) -> dict:
    return {
        "campaign": (ad.get("campaign") or {}).get("name"),
        "ad_group": (ad.get("ad_group") or {}).get("name"),
        "ad_type": ad.get("ad_type"),
        "status": ad.get("status"),
        "headlines": ad.get("headlines"),
        "descriptions": ad.get("descriptions"),
        "display_path": ad.get("display_path"),
        "keywords": [f'{k.get("text")} [{k.get("match_type")}]' for k in ad.get("keywords") or []],
        "negative_keywords": [k.get("text") for k in ad.get("negative_keywords") or [] if isinstance(k, dict)],
        "final_urls": ad.get("final_urls"),
    }


def build_prompt(page: dict, clarity: str | None, brand: str | None) -> str:
    ads = json.dumps([ad_summary(a) for a in page.get("ads", [])], indent=2, ensure_ascii=False)
    return (
        f"# Landing page: {page['normalized_key']}\n\n"
        f"## INPUT 1: Google Ads configurations ({page.get('ad_count', len(page.get('ads', [])))} ads, no performance metrics)\n{ads}\n\n"
        f"## INPUT 2: Microsoft Clarity data\n{_section(clarity)}\n\n"
        f"## INPUT 3: Brand guidelines\n{_section(brand)}\n"
    )


def mock_suggestion(prompt: str) -> str:
    return (
        "<!-- MOCK OUTPUT: no API call made -->\n"
        "## Ad copy / landing page message match\nMock.\n\n## Brand guideline conflicts\nMock.\n\n"
        "## Clarity behavior issues\nMock.\n\n## Prioritized suggestions\nMock.\n"
    )


def call_claude(prompt: str, model: str) -> str:
    import anthropic  # lazy: dry-run/mock work without the SDK or a key

    resp = anthropic.Anthropic().messages.create(  # key from ANTHROPIC_API_KEY
        model=model, max_tokens=16000, system=SYSTEM,
        messages=[{"role": "user", "content": prompt}],
    )
    if resp.stop_reason == "refusal":
        raise RuntimeError("model refused")
    return "".join(b.text for b in resp.content if b.type == "text")


def run(report: Path, clarity_dir: Path | None, brand_file: Path | None, out: Path,
        dry_run: bool = False, mock: bool = False, model: str = MODEL) -> list[Path]:
    data = json.loads(report.read_text(encoding="utf-8"))
    clarity = load_clarity(clarity_dir)
    brand = brand_file.read_text(encoding="utf-8") if brand_file and brand_file.is_file() else None
    out.mkdir(parents=True, exist_ok=True)
    written = []
    for page in data.get("landing_pages", []):
        prompt = build_prompt(page, find_clarity(clarity, page["normalized_key"]), brand)
        name = slug(page["normalized_key"])
        if dry_run:
            path = out / f"{name}.prompt.md"
            path.write_text(f"<!-- SYSTEM -->\n{SYSTEM}\n\n<!-- USER -->\n{prompt}", encoding="utf-8")
        else:
            body = mock_suggestion(prompt) if mock else call_claude(prompt, model)
            path = out / f"{name}.md"
            path.write_text(f"# Suggestions: {page['normalized_key']}\n\n{body}", encoding="utf-8")
        written.append(path)
    return written


def main(argv=None):
    p = argparse.ArgumentParser(prog="lp-suggest")
    p.add_argument("report", type=Path, help="Google Ads landing-page report JSON")
    p.add_argument("--clarity-dir", type=Path, help="folder of per-page Clarity .md files")
    p.add_argument("--brand", type=Path, help="brand guidelines (.md/.json, read as text)")
    p.add_argument("--out", type=Path, default=Path("out"))
    p.add_argument("--dry-run", action="store_true", help="write prompts only, no API call")
    p.add_argument("--mock", action="store_true", help="canned output, no API call")
    p.add_argument("--model", default=MODEL)
    a = p.parse_args(argv)
    for f in run(a.report, a.clarity_dir, a.brand, a.out, a.dry_run, a.mock, a.model):
        print(f)


if __name__ == "__main__":
    sys.exit(main())
