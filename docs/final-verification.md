# Coffee Atlas — archived v1.0.0 engineering certification

**Historical certification:** v1.0.0 passed all tests recorded here. This evidence does **not** certify the modified v1.0.1, v1.0.2, or v1.0.3 releases. For current certification status, see [v1.0.3 maintenance verification](maintenance-verification-v1.0.3.md).

Certification date: November 11, 2026 (America/Los_Angeles). No GitHub repository, account setting or other portfolio project was modified. Hosted GitHub Actions awaits owner-approved publication.

## A. Starting condition

The authoritative release-gated ZIP contained a compact Flask factory, deterministic ranker, nine synthetic catalog records, signed Typeform-compatible webhook, local forms, SQLite snapshots, browser interface, tests, CI and documentation. Archive CRC validation succeeded; all **53** supplied SHA-256 entries matched. The inherited report claimed 186 tests and 95.62% core coverage, but live HTTP, Waitress, browser and lint had not executed. The inherited images were explicitly template previews.

A new Python 3.12.14 virtual environment successfully installed the actual `.[dev]` declarations, including Flask 3.1.3 and Waitress 3.0.2. No dependency substitute or simulated server was used. The first complete attempted run encountered test-runner import failures. After repairing imports, 221 tests passed and two failed: a stale ranking assertion and browser startup.

## B. Engineering changes and regressions

| Location | Confirmed issue / correction | Verification |
|---|---|---|
| `app/routes.py` | Non-ASCII CSRF strings caused `secrets.compare_digest` to raise `TypeError`. Reject non-ASCII tokens before comparison and return the existing 403 response. | Three Unicode-token regressions pass; valid form and multi-tab workflows retained. |
| `scripts/strict_pytest.py`, `pyproject.toml` | File-based runner did not make the repository's `scripts` namespace importable. Add explicit repository path handling and pytest path configuration. | Subprocess regression imports actual repository helper from an external test file. |
| `tests/test_flask_endpoints.py` | Dark/spicy endpoint assertion expected Nightfall before Midnight although both score 8 and title tie order requires Midnight first. Correct the assertion without changing ranking behavior. | Assert both product keys and tied scores; full ranking suite passes. |
| `app/security.py` | Ruff B904 reported ambiguous exception context for a rejected DNS host. Add explicit `from None`. | Ruff passes and origin rejection tests remain green. |
| `scripts/verify_release.py` | Gate lacked formatting enforcement and installed from a source path for its clean check. Require formatting, build/install a wheel in an isolated environment, exercise installed templates/assets/API, and compare two fixed-epoch wheel builds byte for byte. | Negative regression rejects format failure and nonreproducible wheel bytes; clean-install regression inspects wheel target and external working directory; real clean install passes. |
| `tests/test_runtime_certification.py` | Prior server subprocess test covered only Waitress health. Add full real HTTP certification for both Flask and Waitress, including actual mock-sender invocation. | Two complete server-command journeys pass with clean SIGINT shutdown. |
| `tests/test_browser_flow.py` | Expand actual browser coverage and evidence beyond result screenshots. | Desktop and mobile submissions, API/display equality, clipboard, refresh, independent tabs, invalid result and empty form, labels, keyboard focus, console/page errors and overflow checked. Six live captures generated. |
| `tests/test_flask_endpoints.py` | Add explicit unexpected-error disclosure regression. | Forced internal exception produces only generic JSON 500; private marker absent. |
| `pyproject.toml` | Setuptools emitted namespace/data discovery warnings despite explicit app assets. Disable implicit package-data discovery while retaining explicit asset globs. | Build succeeds without the discovery warnings; six required asset paths and installed application verified. |
| `.github/workflows/ci.yml` | Add Ruff formatting enforcement alongside lint. | Configuration inspected; hosted execution deferred until publication authorization. |
| Python files | Apply Ruff's formatter to the existing implementation and tests. | All checked files pass formatting and lint. |
| README and documentation | Remove obsolete execution blockers and preview-image claims. Add tested dependency snapshot and current operations/evidence. | Commands exercised; current claims reviewed against logs. |

The runtime contract, weighted scoring, catalog data, URLs, persistence model and compact scope were retained. No coverage threshold was lowered, no required test was removed, and strict mode still rejects all skips.

### Modified inherited files

- `.github/workflows/ci.yml`
- `README.md`
- `app/__init__.py`
- `app/__main__.py`
- `app/catalog.py`
- `app/config.py`
- `app/preferences.py`
- `app/recommendations.py`
- `app/routes.py`
- `app/security.py`
- `app/storage.py`
- `docs/quality-and-operations.md`
- `docs/release-acceptance.md`
- `docs/screenshots/preference-entry-desktop.png`
- `docs/screenshots/preference-entry-mobile.png`
- `docs/screenshots/preference-form.png`
- `docs/screenshots/recommendation-cards.png`
- `docs/screenshots/recommendations-desktop.png`
- `docs/screenshots/recommendations-mobile.png`
- `docs/technical-case-study.md`
- `pyproject.toml`
- `scripts/send_mock_webhook.py`
- `scripts/strict_pytest.py`
- `scripts/verify_release.py`
- `tests/conftest.py`
- `tests/test_browser_flow.py`
- `tests/test_catalog.py`
- `tests/test_flask_endpoints.py`
- `tests/test_live_http.py`
- `tests/test_mock_sender.py`
- `tests/test_preferences.py`
- `tests/test_recommendations.py`
- `tests/test_release_gate.py`
- `tests/test_remediation_regressions.py`
- `tests/test_round3_fixes.py`
- `tests/test_round4_config.py`
- `tests/test_security_config.py`
- `tests/test_storage.py`
- `tests/test_templates.py`
- `tests/test_waitress_entrypoint.py`

New files include `tests/test_runtime_certification.py`, `requirements-verified.txt`, this report, screenshot provenance and the sanitized evidence directory. The final SHA-256 manifest provides the complete authoritative inventory.

## C. Observed verification

| Command/check | Observed outcome |
|---|---|
| Archive CRC and supplied manifest | Passed; all 53 original entries match |
| `python -m pip install -e '.[dev]'` | Successfully installed in a clean Python 3.12.14 environment |
| `python -m pip check` | No broken requirements found |
| `python -m compileall -q app tests scripts` | Exit 0 |
| Gate core suite | **190 passed**, 0 skips; **95.62%** core coverage (threshold 90%) |
| `python scripts/strict_pytest.py -q --cov=app --cov-report=term-missing --cov-fail-under=80` | **233 passed**, 0 failures, 0 skips; **95.06%** app coverage |
| `python -m ruff check .` | All checks passed |
| `python -m ruff format --check .` | All checked files formatted |
| Wheel build and fixed-epoch rebuild | Equal SHA-256 bytes; required catalog, templates, JS and CSS present |
| Clean wheel installation | New virtual environment; imports from installed site-packages outside source checkout; health, home, static CSS/JS and three-result preview succeed |
| Runtime dependency audit | Eight installed runtime distributions checked; no known vulnerabilities returned |
| `python scripts/verify_release.py` | **Exit 0; `local_release_gate_passed`** |

The gate used `COFFEE_BROWSER_PATH` to select the official Playwright headless-shell executable. Exact commands and observed subprocess output are retained in `docs/evidence/release-console.txt`; the machine-readable verdict is `docs/evidence/release-report.json`. Coverage is measured in the parent test process; subprocess server code is not falsely counted as covered.

## D. Actual runtime and browser evidence

Both `python -m app` (Waitress) and `python -m flask --app app:create_app run --host 127.0.0.1 --port <test-port>` bound loopback TCP ports and served real HTTP. The tests created forms, submitted CSRF/nonces, followed the 303 redirect, found exactly three cards, compared API output to SQLite rows, and replayed forms idempotently. Signed JSON and the actual `scripts/send_mock_webhook.py` command succeeded; invalid/missing signatures returned 401, malformed structured events 422, oversized requests 413, missing CSRF 403, and invalid/missing resources controlled 400/404. Both processes exited cleanly with SIGINT and no uncaught traceback. Flask's expected development-server warning is confined to the development command.

Chromium Headless Shell **141.0.7390.37** with Playwright **1.56.0** completed the real desktop and mobile form journeys. Desktop used 1440×1000, mobile 390×844. The richer desktop decaf profile ranked Mistline Decaf (17), Evening Decaf (3), Midnight Decaf (3), consistent with persisted/API scoring. The mobile decaf-only profile produced three tied 3-point suggestions in title order. Explanations and score breakdowns agreed with the displayed cards. Refresh retained the same record; independent tabs created different records; clipboard restoration and example cart URL construction succeeded. Browser JavaScript/page errors and unexpected console errors were absent during the successful workflows. Controlled invalid navigation and empty submission were also exercised.

All six publication PNGs were captured over live HTTP during this session, visually reviewed, and replace the earlier template previews:

- `docs/screenshots/preference-entry-desktop.png`
- `docs/screenshots/preference-entry-mobile.png`
- `docs/screenshots/preference-form.png`
- `docs/screenshots/recommendations-desktop.png`
- `docs/screenshots/recommendations-mobile.png`
- `docs/screenshots/recommendation-cards.png`

The screenshot provenance JSON records browser/test identity, viewports and per-image hashes. Desktop and mobile layouts had no horizontal overflow. Label associations, named fieldsets, keyboard focus and the intended contrast pairs passed basic checks.

## E. Final independent audit, security and confidentiality

Fresh source review covered routes, configuration, preferences, scoring, catalog validation, HMAC, storage transactions, filesystem handling, templates/JS, sender isolation, packaging, CI and documentation. The independent Unicode-CSRF probe reproduced a real exception, which was corrected and covered before final certification. The complete gate was rerun following the correction. No confirmed critical or high-severity defect remains in the documented local demonstration scope.

Tests cover missing/tampered HMAC signatures; CORS allowlists; symlink paths; owner-only POSIX DB permissions; foreign-key enforcement/orphans; concurrent idempotent submissions; changed-payload conflicts; catalog/algorithm snapshot retention; caffeine filtering; deterministic tie order; malformed/unknown/repeated inputs; escaping; generic internal errors; and absence of debug routes. The catalog remains synthetic and unchanged. Free-text notes and raw payload/contact data are not saved or returned through the result API. All merchant-style links target reserved `shop.example`.

The publication tree was reviewed and scanned for credentials, real customer submissions, private storefront identifiers and confidential commercial content. No proposal, partner prices, margin calculations, negotiation material, private keys or real storefront credentials are included. Test secrets are conspicuously synthetic. Prices and variant IDs in the validated catalog are fictional demonstration data.

This is a loopback application using synthetic data, without end-user authentication, automated retention or supported public production hosting. Filesystem protections assume an owner-controlled directory. Basic accessibility checks are not a complete screen-reader audit. Local execution covers Python 3.12.14; 3.11/3.13 are declared and CI-configured but were not locally executed. Docker was unavailable and remains optional. Hosted Actions has not executed and will follow separately authorized publication. None of these is represented as completed production delivery.

## F. Portfolio assessment

These are my judgments about the finished artifact and its evidence, not an external certification score.

| Target role | Assessment | Strongest evidence |
|---|---|---|
| Software Engineer | **9.2/10** | Tested Flask boundaries, deterministic algorithm, transactions, security regressions, real HTTP/browser evidence and packaging |
| Data Analyst | **8.1/10** | Controlled data contract, transparent scoring contributions and reproducibility; no measured business dataset or statistical outcome study |
| IT Support Specialist | **8.5/10** | Environment recovery, dependency diagnosis, safe configuration, runtime troubleshooting and operational documentation |
| Operations Coordinator | **9.0/10** | Explicit requirements/scope matrix, reproducible release criteria, traceable evidence and approval-controlled publication handoff |

## G. Publication decision

**PASS — Ready for publication approval.** All required local release checks passed, including real Flask and Waitress serving, HTTP persistence/API flows, Chromium submissions, zero-skips tests, coverage, lint/format, reproducible wheel and clean install. Final archive integrity, confidentiality and manifest checks accompany the deliverable. No GitHub mutation was performed or authorized by this certification.

## H. Reproduction and deliverables

The delivered ZIP contains the full independent source, tests, CI, catalog, examples, documentation, authentic screenshots and evidence. The standalone wheel is also supplied. The manifest covers each source file plus the downloadable artifacts. ZIP members use stable ordering, fixed timestamps and normalized file modes; two separately produced ZIPs were compared for byte identity.

For Python-package reproduction use `requirements-verified.txt` before the README's editable install. Build tools remain declared in `pyproject.toml`. Wheel byte comparisons use `SOURCE_DATE_EPOCH=1762819200`. The clean release environment successfully downloaded packages; it does not depend on the former environment's missing packages. No account credentials, external storefront or paid AI service is needed to execute the demo.
