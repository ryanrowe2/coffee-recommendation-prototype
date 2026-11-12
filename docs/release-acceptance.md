# Release acceptance and closure protocol

This document is the **single decision rule** for the portfolio release. It replaces repeated open-ended "find and fix everything" passes with independent, reproducible exit criteria. It does not claim that software can be proved free of every possible defect.

## States and exit codes

Run from the repository root:

```bash
python scripts/verify_release.py --offline  # offline evidence; returns 2 (PARTIAL)
python -m pip install -c requirements-verified.txt setuptools wheel
python -m pip install --no-build-isolation -c requirements-verified.txt -e '.[dev]'
python -m playwright install chromium
python scripts/verify_release.py            # complete local gate; returns 0 only if every check passes
```

The verifier writes `.verification/release-report.json`, including every executed stage and its observed outcome. That generated file is deliberately excluded from Git, so results aren't accidentally presented as fresh evidence in another environment.

| Verdict | Meaning | Action |
|---|---|---|
| `partial_offline_only` (exit 2) | Unit/algorithm/security/storage checks and packaging passed; network-facing behavior was not tested | Move to dependency-enabled environment; **do not restart generic code audits** |
| `blocked_dependencies` (exit 2) | Offline checks passed; essential runtime/tools missing | Install dependencies and Chromium; rerun same gate |
| `failed` (exit 1) | An executed check failed | Repair **only the reproduced failing behavior**, add regression, rerun gate |
| `local_release_gate_passed` (exit 0) | All required offline, lint, Flask, Waitress, HTTP, browser, wheel and clean-install checks passed with **zero skipped tests** | Present report and package for publication approval |

For a machine with Docker and network/package access, the QA environment can also be built from the checkout (this image has not been built in the offline authoring environment):

```bash
docker build -f Dockerfile.verify -t coffee-verifier .
docker run --rm coffee-verifier
```

Both commands must succeed; do not treat the existence of a Dockerfile as evidence of a successful container test.

**No skipped or missing mandatory integration tests are allowed in strict mode**: `scripts/strict_pytest.py` turns collection-time module skips and individual test skips into failures; the full gate requires named Flask, HTTP, Waitress, and Chromium tests to be collected. The release verifier separately checks mandatory source files and function names before even attempting dependency installation. The dedicated `tests/test_release_gate.py` regression suite proves that a missing integration dependency cannot be mistaken for a complete pass.

## Finite technical criteria

A candidate can receive a local release pass only when all of these occur within the *same code revision*:

1. Compilation succeeds.
2. The six independent core modules have at least 90% statement coverage, with all offline tests passing.
3. Source-wheel build succeeds and the expected templates, JS, CSS and synthetic catalog are present.
4. Pinned Flask and Waitress and required test/lint/build/browser tools are installed.
5. Ruff lint and formatting checks succeed.
6. All tests execute, including Flask endpoints, real HTTP requests, the Waitress subprocess and the actual Chromium workflow, with **no skips** and >=80% overall app coverage.
7. A clean virtual-environment wheel installation imports `app` from **installed site-packages**, not from the checkout, and returns HTTP 200 from the health endpoint.
8. No known critical or high-severity problem remains, and the publication archive contains no internal proposal, real customer responses, credentials, proprietary store IDs, or private commercial terms.

If a test fails, fix its specific cause; avoid changing unrelated features. Repeat a focused regression and the same verifier. The target is a verified candidate, not an endless succession of audits.

## GitHub sequence (no circular approval condition)

The repository must not be created or modified until expressly approved by the account owner.

- **Before approval:** obtain a passing local release gate using a runtime with network/package access. Inspect the report and final archive. **Do not claim GitHub CI ran**.
- **After approval/publication:** GitHub Actions checks the Python matrix and runs the strict full gate in a Chromium-enabled job. Verify the resulting checks and captured *live-server* screenshots. Resolve actual CI failures before treating the published repository as operationally verified.
- **No endless re-audits:** a green gate plus green published CI and no known high-priority defects is the practical stopping condition. Later fixes are ordinary maintenance, not a reason to reopen historical closed findings.

## Certification status

The original **v1.0.0** release passed its local gate on November 11, 2026; see the [archived certification](final-verification.md). That historical record does **not** certify later revisions. The **v1.0.3 candidate independently passed its own full dependency-enabled gate**, including verification from the final extracted ZIP: **264 tests passed with zero skips, 95.14% application coverage, and exit code 0**. See [current v1.0.3 maintenance verification](maintenance-verification-v1.0.3.md) and the [bundled gate result](evidence/v1.0.3-local-gate.json). The local publication-approval checkpoint is therefore satisfied. **Hosted GitHub Actions remains pending** owner-authorized publication.

This repository remains a self-contained local proof of engineering work with synthetic data.
