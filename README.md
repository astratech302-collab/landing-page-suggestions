# landing-page-suggestions

Small CLI. For each landing page in a Google Ads landing-page report, builds a prompt from
ad configs + a Microsoft Clarity `.md` + brand guidelines, asks Claude, and writes one
suggestions `.md` per page. No web UI, no database.

## Setup

```bash
uv venv && uv pip install -e '.[test]'     # Python 3.12+
export ANTHROPIC_API_KEY=...               # only for real runs
```

## Run

```bash
# write assembled prompts only, no API call, no key needed
.venv/bin/lp-suggest examples/sample-report.json --clarity-dir examples/clarity --brand examples/brand.md --out out --dry-run

# canned output, no API call (tests the output path)
.venv/bin/lp-suggest examples/sample-report.json --mock --out out

# real run (default model claude-opus-5-5, override with --model)
.venv/bin/lp-suggest examples/sample-report.json --clarity-dir examples/clarity --brand examples/brand.md --out out
```

Dry-run writes `out/<page-slug>.prompt.md`; otherwise `out/<page-slug>.md`. Slug is derived
from the report's `normalized_key`. `examples/sample-report.json` is a copy of the
google-ads-integration sample (3 pages).

## Input contracts

1. **Ads report JSON** (positional). Reads `landing_pages[]` -> `normalized_key`, `ad_count`,
   `ads[]` (campaign/ad group name, `ad_type`, `status`, `headlines`, `descriptions`,
   `display_path`, `keywords`, `negative_keywords`, `final_urls`). `unmapped_ads` and
   `data_gaps` are ignored. The report has no performance metrics; the prompt says so.
2. **Clarity folder** (`--clarity-dir`): one `.md` per page, free text, passed verbatim.
   Matched to a report page by, in order:
   - front-matter `url: https://...` (compared after normalising: lowercase host, no query/fragment, no trailing slash), else
   - filename stem equal to the slug of `host+path` (`example-com-sale.md`) or of `path` only (`sale.md`; `/` -> `home.md`).

   A page with no file is marked **MISSING**; an empty file is marked **EMPTY**. The model
   is told to say so rather than invent data. Format change later: edit `build_prompt`.
3. **Brand guidelines** (`--brand`): any text file (.md/.json), passed verbatim as free text.
   Missing/unreadable path -> MISSING; empty -> EMPTY.

## Output

Each suggestions file has sections: ad copy / landing page message match, brand guideline
conflicts, Clarity behavior issues, prioritized suggestions.

## Assumptions

- Pages are processed sequentially, one API call each; no retries beyond the SDK default.
- Pages that differ only by query string or `m.` subdomain stay separate (report already split them), but a Clarity file matches by path, ignoring query.
- Whole brand/Clarity text is sent unchunked; very large files are not truncated or split.
- Uses the model default thinking/effort; no tuning.

## Tests

```bash
.venv/bin/pytest
```
