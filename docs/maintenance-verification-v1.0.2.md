# Coffee Atlas — v1.0.2 maintenance verification

**Current status: Source and QA infrastructure fixes implemented; full v1.0.2 runtime certification pending.**

## Provenance

The stored 233-pass, 95.06%-coverage release certificate and Chromium screenshots refer to
**v1.0.0**, not v1.0.2. The intervening **v1.0.1** package was not full-runtime certified.
This release is based on v1.0.1 and preserves the synthetic catalog, Flask routes, UI,
and deterministic scorer without functional feature additions.

## Changes addressing the v1.0.1 independent audit

| Finding | v1.0.2 remediation |
|---|---|
| Local HTTP test proxy inheritance | Both affected test modules call the explicit `loopback_opener()` helper, which installs `ProxyHandler({})`; a regression uses a proxy interception server |
| Contaminated clean-wheel health check | Fresh install smoke uses `isolated_smoke_environment()` and requires `Config.from_env().catalog_path` to point inside the installed wheel assets |
| QA Docker image missing Node | Pinned Python Bookworm image installs system `nodejs` and checks `node --version` at build time |
| Distributed wheel timestamp mismatch | The standalone v1.0.2 wheel is built from these sources using `SOURCE_DATE_EPOCH=1762819200`, matching the verifier's canonical epoch |
| Historical certification wording | Standalone operational docs and case study explicitly name the v1.0.0 certification and the v1.0.2 pending gate |
| Floating QA versions | Docker base is pinned to an immutable registry digest, CI selects `ubuntu-24.04`, and the QA Python dependency snapshot is used as pip constraints in CI and Docker |

The pinned Docker digest and dependency snapshot must be deliberately updated for
security and supported platform changes. Debian OS packages and Playwright downloads
are not hash-locked by this repository. Multi-interpreter constraints compatibility
still requires the GitHub CI matrix to execute after publication approval.

## Certification checklist

To certify **this exact v1.0.2 package**, install the development dependencies and
Chromium in a supported online environment, then execute:

```bash
python -m pip install -c requirements-verified.txt setuptools wheel
python -m pip install --no-build-isolation -c requirements-verified.txt -e '.[dev]'
python -m playwright install chromium
python scripts/verify_release.py
```

The strict release gate must exit 0 with no skipped integration tests, >=80% whole-app
coverage, Ruff lint/format, running Flask and Waitress, real HTTP and Chromium
journeys, and installed wheel asset tests. `--offline` deliberately exits 2 even
when all independently runnable checks pass. GitHub Actions remains unrun before
explicit owner authorization to publish.

## Local verification evidence

The v1.0.2 source-archive checks recorded **208 passing core and infrastructure tests**,
**5 Flask-dependent modules skipped**, **95.73% core coverage**, successful
compilation, byte-identical reproducible wheels, and ZIP/screenshot integrity.
The strict release gate returned **`BLOCKED_DEPENDENCIES` (exit 2)** because
Flask, Waitress, Ruff, and the Python build tool were not available in that
execution environment. The separate remediation report was not part of this
public repository; these are the self-contained verification facts relevant to
that archived release. Do not treat v1.0.0 results as v1.0.2 runtime evidence.

For the succeeding maintenance candidate, see
[v1.0.3 maintenance verification](maintenance-verification-v1.0.3.md).
