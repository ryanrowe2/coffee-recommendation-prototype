# Coffee Atlas — v1.0.1 maintenance verification

**Status: CHANGES IMPLEMENTED; FULL RUNTIME RE-CERTIFICATION REQUIRED.**

This is a targeted maintenance release based on the independently certified **v1.0.0** artifact. Its previously recorded 233-pass/95.06%-coverage Work result is preserved under [`final-verification.md`](final-verification.md) and `evidence/`, but **those logs apply only to v1.0.0**, not to these changed sources. No GitHub account or repository was modified.

## Closed findings and evidence

| Independent audit finding | v1.0.1 correction | Regression validation |
|---|---|---|
| Required integration tests could disappear without failing the gate | Mandatory filename and function checks before any release stage; separate pytest collection check for required Flask/HTTP/Waitress/Chromium test IDs; CI server-only and full-release inventory modes | Missing/renamed file and missing-collected-browser tests fail; passing ordinary focused runner behavior retained |
| Open forms lose their CSRF cookie after a server restart | 256-bit randomly generated session signing key persisted once in the owner-only SQLite DB under an immediate write transaction; stable across restart and concurrent first-start processes | Store restart, independent DB isolation, concurrency, malformed saved key; Flask cookie restart test added (runtime execution pending) |
| Unexpected HTTP Host headers were accepted | Flask `TRUSTED_HOSTS` now allows only `localhost` and `127.0.0.1`; live Waitress still binds to 127.0.0.1 | Flask test asserts allowed hosts return 200 and unexpected Host headers return 400 (runtime execution pending) |
| CI actions used mutable tags | Three GitHub-hosted actions upgraded to Node-24-compatible v7 releases pinned to verified 40-hex commit SHAs; `persist-credentials: false` on both checkouts; monthly Dependabot review | CI YAML pinned-ref and inventory tests pass; hosted CI execution requires post-approval publication |

Session key data is retained only in the configured SQLite database. The database is excluded from Git and the publication ZIP; its access controls remain 0600 on POSIX. Deleting a local database rotates its key, invalidating old cookies. No external identity, authentication or production public hosting was added.

## Independently executed here

Environment: Python 3.13 (offline; Flask, Waitress, Ruff and build frontend unavailable).

```text
python -m pytest -q --ignore=tests/test_flask_endpoints.py \
  --ignore=tests/test_live_http.py \
  --ignore=tests/test_runtime_certification.py \
  --ignore=tests/test_waitress_entrypoint.py \
  --ignore=tests/test_browser_flow.py
201 passed

python scripts/verify_release.py --offline
PARTIAL_OFFLINE_ONLY (exit 2)

# Offline release-gate stages:
mandatory_integration_inventory: passed
compile: passed
offline_core: passed (95.73% coverage, above 90% minimum)
wheel_content: passed (two byte-identical builds; six assets present)

python scripts/strict_pytest.py --require-integration-tests -q tests/test_security_config.py
exit 1: required Flask, HTTP, Waitress, and browser tests not collected
```

The built distribution is version **1.0.1**. Packaging checks, checksums and the extracted ZIP integrity are documented in the accompanying verification report and SHA-256 manifest.

## Remaining certification requirements

Run in a dependency-enabled environment, from the **v1.0.1** ZIP (not v1.0.0):

```bash
python -m pip install -e '.[dev]'
python -m playwright install chromium
python scripts/verify_release.py
```

The full gate must return exit **0**, with 0 skipped tests, all mandatory integration test IDs collected, at least 80% whole-app coverage, Ruff lint/format, a real Flask/Waitress/HTTP/Chromium journey, a reproducible wheel and a clean installation. Until that occurs, this changed revision is **not represented as newly certified**, and hosted CI also has not run. The prior passing Work certification is historical evidence, not a substitute for these checks.
