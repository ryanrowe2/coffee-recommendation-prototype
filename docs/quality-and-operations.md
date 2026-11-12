# Validation, security, and local operations

The original v1.0.0 release passed real Flask, Waitress, HTTP and Chromium verification; see its [archived certification](final-verification.md). The **current v1.0.3 release also passed** its full dependency-enabled gate on November 11, 2026: **264 tests passed, zero skips; 95.14% application coverage; strict exit 0**. See [v1.0.3 maintenance verification](maintenance-verification-v1.0.3.md), the bundled [machine-readable gate result](evidence/v1.0.3-local-gate.json), and [release acceptance](release-acceptance.md). Hosted GitHub Actions remains unverified until owner-authorized publication.

## Repeat verification

```bash
python -m pip install -c requirements-verified.txt setuptools wheel
python -m pip install --no-build-isolation -c requirements-verified.txt -e '.[dev]'
python -m playwright install chromium
python scripts/verify_release.py
```

The strict command requires zero skipped tests, at least 90% core coverage and 80% complete application coverage, Ruff lint and formatting, byte-identical wheel rebuilds, package assets, a clean wheel installation, live Flask/Waitress workflows and a real browser journey. Offline mode deliberately exits 2. Ordinary pytest may skip unavailable integration modules; the strict runner rejects those skips.

`requirements-verified.txt` records the pinned Python 3.12 QA validation environment and is used as a pip constraints input by the current Docker and CI configurations. It is not a hash-locked multi-platform dependency artifact. `pyproject.toml` declares supported Python 3.11–3.13 dependencies. Hosted CI covers that interpreter matrix after publication. The v1.0.0 and current v1.0.3 local certifications were performed on Python 3.12.14. The declared Python 3.11/3.13 CI matrix has not yet run on GitHub.

## Screenshot provenance

The six PNGs in `docs/screenshots/` are verified live-loopback-HTTP Chromium captures associated with the v1.0.3 certification. The final evidence compares them with the earlier v1.0.0 captures and reports **identical pixels**, and their retained SHA-256 hashes match the earlier screenshot set. They therefore depict an **unchanged interface**; their presence in the v1.0.3 package does not indicate a visual redesign. The capture metadata and hashes are in [`screenshots/provenance.json`](screenshots/provenance.json). They show the independent Coffee Atlas demonstration with a synthetic catalog. No original merchant assets or storefront captures are included. The automated journey captures desktop/mobile entry and results pages, the form and the card grid. It verifies real submissions, rankings against the API, clipboard actions, refresh, multi-tab independence, label associations, keyboard focus, error behavior and absence of horizontal overflow. Tests also check intended text/background contrast pairs. This is basic accessibility validation, not a complete assistive-technology audit.

## Operational commands

```bash
python -m app
# Alternate Flask development server:
python -m flask --app app:create_app run --host 127.0.0.1 --port 5050
```

Both commands were exercised as subprocesses over real HTTP during **v1.0.3 certification**, as recorded in the current maintenance verification and gate evidence. The Waitress entry point binds only to loopback. Use synthetic data; local SQLite records remain until manually deleted. `.local_data/`, databases, caches, builds, environments and generated verification output are ignored by Git and excluded from the publication ZIP.

For the signed example, set `TYPEFORM_WEBHOOK_SECRET` and `TYPEFORM_FORM_ID` as shown in the README and run `python scripts/send_mock_webhook.py`. The **v1.0.3 runtime tests** executed this actual command against both running servers. Duplicate delivery returns success without overwriting the saved snapshot.

## Configuration contract

| Variable | Meaning |
|---|---|
| `APP_MODE` | `local` (default) or `production`; only local has a supported serving entry point |
| `PORT` | Waitress TCP port, default 5050; allowed range 1024–65535 |
| `APP_DB_PATH` | SQLite file, default `.local_data/recommendations.sqlite3`; rejects symlink path components |
| `APP_CATALOG_PATH` | Optional catalog JSON override; validated before serving |
| `TYPEFORM_WEBHOOK_SECRET` | Webhook signing secret; configured values require 24+ printable characters without surrounding whitespace |
| `TYPEFORM_FORM_ID` | Optional exact form match in local mode; required in production-mode configuration |
| `ALLOWED_ORIGINS` | Empty by default; comma-separated canonical HTTPS origins for read-only API CORS |
| `COFFEE_BROWSER_PATH` | Optional Chromium executable for tests; v1.0.3 certification used the official Playwright headless shell |

`.env.example` documents settings; the application reads actual environment variables and does not automatically load `.env`. Do not commit credentials.

## Verified controls

| Boundary | Checks exercised |
|---|---|
| Webhook | HMAC-SHA256, tampering/missing signatures, malformed payloads, explicit event/form IDs, bounded requests, duplicate/conflicting submissions |
| Local form | CSRF including non-ASCII rejection, hashed per-form nonces, independent tabs, concurrent retries, unknown/repeated parameters |
| Persistence | SQLite transactions, foreign keys, orphan detection, catalog/algorithm snapshots, private POSIX file permissions, symlink rejection |
| Recommendations | Caffeine eligibility, active catalog filtering, stable tie order, score/explanation consistency, exactly three results |
| Output | Jinja escaping, CSP and other headers, restricted response identifiers, controlled 400/403/404/409/413/422 outcomes, generic 500 responses |
| Mock sender | Loopback-only URL, redirects disabled, inherited proxies disabled; actual sender command against both servers |
| Data handling | No raw webhook body, optional notes, contact fields or raw-note hashes in saved/public records |
| Outbound links | Validated synthetic variants/handles, reserved `https://shop.example` demonstration URLs |
| Packaging | Required data/templates/styles/scripts, reproducible wheel, clean installation outside checkout |

The historical v1.0.0 runtime dependency advisory audit found no known vulnerabilities in the eight checked distributions on November 11, 2026. Its machine-readable results are in `docs/evidence/`. This observation is tied to the checked versions and advisory response.

The app is a loopback portfolio demonstration. It has no user authentication or response-retention service. The local Flask session signing key is generated securely once and stored in the owner-controlled SQLite database, allowing an open form to survive an application restart; deleting that database intentionally resets it. Host headers are restricted to `127.0.0.1` and `localhost`. It assumes an owner-controlled filesystem. Public operation would require a separately engineered access, privacy, deployment, rate-limiting and lifecycle model. The original production commerce and AI proposal remains outside the implemented scope.
