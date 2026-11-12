# Coffee Atlas — v1.0.3 maintenance verification

**Status: full v1.0.3 runtime certification passed.**

The November 11, 2026 dependency-enabled Work session recovered the authoritative
v1.0.3 ZIP (SHA-256 `221a5da61d9e95d694f40a5eb462c3de149bac5019023e15f8cf6b32112d15c5`)
and verified all 70 member hashes plus the two supplied artifact hashes.
The inherited dependency blocker was eliminated with a clean Python 3.12.14 venv
and the exact `requirements-verified.txt` constraints.

## Corrections and source identity

The runtime application, catalog, templates and frontend assets are unchanged
from the authoritative v1.0.3 source. Ruff formatting corrected two QA files:
`scripts/verify_release.py` and `tests/test_release_hardening.py`. Documentation,
screenshot provenance and the release-status regression assertion now record the
executed v1.0.3 certification. No material application change or version bump was
needed. Original CORS validation and SQLite connection-cleanup fixes remain intact.

## Executed results

| Check | Result |
|---|---|
| Strict complete tests | 264 passed; zero skips |
| Whole application coverage | 95.14%; threshold 80% |
| Six core modules | 95.73%; threshold 90% |
| Ruff lint / format | Passed |
| Compilation | Passed |
| Actual Flask and Waitress subprocess HTTP workflows | Passed |
| Chromium desktop 1440 × 1000 and mobile 390 × 844 | Passed |
| Clipboard, API, refresh, labels, keyboard, layout, invalid input | Passed |
| Reproducible wheels and six required package resources | Passed |
| New isolated venv wheel installation and installed app smoke | Passed |
| Strict release gate | Exit 0; LOCAL_RELEASE_GATE_PASSED |

Browser captures are from real HTTP requests to Werkzeug serving `app.create_app`,
with Playwright 1.56.0 and official Chromium Headless Shell 141.0.7390.37.
The system Chromium could not start due to restricted Unix socket creation;
the official headless shell completed the actual browser tests.

## Reproduce

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -c requirements-verified.txt setuptools wheel
python -m pip install --no-build-isolation -c requirements-verified.txt -e '.[dev]'
python -m playwright install chromium
python scripts/verify_release.py
```

In a restricted runtime, select the official headless shell using
`COFFEE_BROWSER_PATH` and set `PLAYWRIGHT_BROWSERS_PATH` to a directory without a
full Chromium installation so the test's external-browser selection is used.
No tests, thresholds or mandatory inventory checks were weakened.

The final delivered ZIP is extracted separately and receives its own full gate.
Its external JSON/log and SHA-256 manifest bind that result to the finished
archive. These avoid a circular archive hash inside the archive itself.
The pre-certification reports in historical documents retain their original scope.

**Current publication status (November 12, 2026):** The original 264-test table above remains the historical local v1.0.3 certification record. The approved project is now published. Following a narrowly scoped favicon and CI-artifact fix in [PR #4](https://github.com/ryanrowe2/coffee-recommendation-prototype/pull/4), [hosted GitHub Actions on protected `main`](https://github.com/ryanrowe2/coffee-recommendation-prototype/actions/runs/43185857273) passed all four required jobs: **265 tests, zero skips, 95.16% application coverage**, and an uploaded artifact containing six screenshots and the release-gate JSON. The local archive and hosted main revisions have distinct test counts; both results are preserved with their provenance.
