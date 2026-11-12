"""One-command, fail-closed release assessment with independent stage evidence.

Usage: python scripts/verify_release.py [--offline] [--report PATH]

Default mode performs independent offline checks, then requires real Flask,
Waitress, Ruff, Chromium, and a full no-skips HTTP/browser validation. The
`--offline` option runs only checks possible without the HTTP dependencies and
returns an explicitly *partial* verdict (exit 2), never a release pass.

No repository changes or network traffic occur during the offline checks.
Strict mode may fetch dependencies when building an isolated installation.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import traceback
import zipfile

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from scripts.strict_pytest import check_required_test_sources  # noqa: E402

HTTP_VERSIONS = {"Flask": "3.1.3", "waitress": "3.0.2"}
RELEASE_TOOLS = ("pytest", "pytest-cov", "ruff", "playwright", "build")
BLOCKED_TEST_FILES = (
    "tests/test_flask_endpoints.py",
    "tests/test_live_http.py",
    "tests/test_runtime_certification.py",
    "tests/test_waitress_entrypoint.py",
    "tests/test_browser_flow.py",
)
CORE_MODULES = (
    "app.catalog",
    "app.config",
    "app.preferences",
    "app.recommendations",
    "app.security",
    "app.storage",
)
EXPECTED_WHEEL_ASSETS = (
    "app/data/catalog.json",
    "app/templates/index.html",
    "app/templates/results.html",
    "app/templates/base.html",
    "app/static/style.css",
    "app/static/app.js",
)


def run(name: str, cmd: list[str], *, env: dict[str, str] | None = None, cwd: Path = ROOT) -> dict:
    print(f"\n[{name}] $ {' '.join(cmd)}", flush=True)
    try:
        result = subprocess.run(
            cmd,
            cwd=cwd,
            env=env,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=False,
            timeout=360,
        )
    except subprocess.TimeoutExpired as exc:
        return {"name": name, "status": "failed", "message": f"Timed out after {exc.timeout} seconds"}
    print(result.stdout[-10000:], end="\n", flush=True)
    return {
        "name": name,
        "status": "passed" if result.returncode == 0 else "failed",
        "exit_code": result.returncode,
        "output_tail": result.stdout[-2500:],
    }


def preflight() -> list[str]:
    errors = []
    for name, required in HTTP_VERSIONS.items():
        try:
            actual = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            errors.append(f"{name}=={required} not installed")
        else:
            if actual != required:
                errors.append(f"{name} version {actual} != required {required}")
    for name in RELEASE_TOOLS:
        try:
            importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            errors.append(f"{name} not installed")
    if shutil.which("node") is None:
        errors.append("Node.js not available for the clipboard regression test")
    try:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as pw:
            executable = Path(pw.chromium.executable_path)
            if not executable.exists() and not (
                os.environ.get("COFFEE_BROWSER_PATH") or shutil.which("chromium")
            ):
                errors.append("Chromium browser executable unavailable")
    except (ImportError, RuntimeError, OSError) as exc:
        errors.append(f"Playwright Chromium startup check failed: {type(exc).__name__}")
    return errors


def build_wheel() -> dict:
    with tempfile.TemporaryDirectory(prefix="coffee-wheel-") as work:
        result = run(
            "wheel_build",
            [
                sys.executable,
                "-m",
                "pip",
                "wheel",
                "--no-deps",
                "--no-build-isolation",
                "--wheel-dir",
                work,
                ".",
            ],
            env={**os.environ, "SOURCE_DATE_EPOCH": "1762819200"},
        )
        if result["status"] == "failed":
            return result
        wheels = list(Path(work).glob("coffee_recommendation_prototype-*.whl"))
        if len(wheels) != 1:
            return {"name": "wheel_content", "status": "failed", "message": "Expected exactly one wheel."}
        first_hash = hashlib.sha256(wheels[0].read_bytes()).hexdigest()
        repeat = Path(work) / "repeat"
        repeated = run(
            "wheel_rebuild",
            [
                sys.executable,
                "-m",
                "pip",
                "wheel",
                "--no-deps",
                "--no-build-isolation",
                "--wheel-dir",
                str(repeat),
                ".",
            ],
            env={**os.environ, "SOURCE_DATE_EPOCH": "1762819200"},
        )
        if repeated["status"] != "passed":
            return repeated
        rebuilt = list(repeat.glob("*.whl"))
        if len(rebuilt) != 1 or hashlib.sha256(rebuilt[0].read_bytes()).hexdigest() != first_hash:
            return {"name": "wheel_reproducibility", "status": "failed", "message": "Wheel bytes differ."}
        with zipfile.ZipFile(wheels[0]) as package:
            names = set(package.namelist())
            missing = sorted(set(EXPECTED_WHEEL_ASSETS) - names)
        if missing:
            return {"name": "wheel_content", "status": "failed", "message": f"Missing assets: {missing}"}
        return {
            "name": "wheel_content",
            "status": "passed",
            "wheel_bytes": wheels[0].stat().st_size,
            "sha256": first_hash,
            "byte_reproducible": True,
            "expected_assets_checked": len(EXPECTED_WHEEL_ASSETS),
        }


def isolated_smoke_environment(db_path: Path) -> dict[str, str]:
    """Prevent external application settings from contaminating wheel validation.

    Preserve ordinary process settings needed for certificates, proxies for pip,
    and the OS, while explicitly removing Python import and app overrides.
    """
    denied = ("APP_", "TYPEFORM_", "COFFEE_", "FLASK_")
    exact = {"ALLOWED_ORIGINS", "PORT", "PYTHONPATH", "PYTHONHOME", "PYTHONUSERBASE", "VIRTUAL_ENV"}
    env = {
        key: value
        for key, value in os.environ.items()
        if key not in exact and not any(key.startswith(prefix) for prefix in denied)
    }
    env.update({"APP_MODE": "local", "APP_DB_PATH": str(db_path)})
    return env


def fresh_install_check() -> dict:
    with tempfile.TemporaryDirectory(prefix="coffee-release-venv-") as work:
        venv_path = Path(work) / "venv"
        venv = run("clean_venv", [sys.executable, "-m", "venv", str(venv_path)])
        if venv["status"] != "passed":
            return venv
        py = venv_path / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
        wheel_dir = Path(work) / "dist"
        build = run(
            "fresh_wheel_build",
            [sys.executable, "-m", "build", "--wheel", "--no-isolation", "--outdir", str(wheel_dir)],
            env={**os.environ, "SOURCE_DATE_EPOCH": "1762819200"},
        )
        if build["status"] != "passed":
            return build
        wheels = list(wheel_dir.glob("*.whl"))
        if len(wheels) != 1:
            return {"name": "fresh_install", "status": "failed", "message": "Expected exactly one wheel."}
        install = run(
            "fresh_install",
            [str(py), "-m", "pip", "install", "-c", str(ROOT / "requirements-verified.txt"), str(wheels[0])],
        )
        if install["status"] != "passed":
            return install
        env = isolated_smoke_environment(Path(work) / "fresh.sqlite3")
        return run(
            "fresh_health",
            [
                str(py),
                "-c",
                "import app, sys; from pathlib import Path; "
                "from app.config import Config; "
                "installed=Path(app.__file__).resolve(); "
                "assert installed.is_relative_to(Path(sys.prefix).resolve()), installed; "
                "catalog=installed.parent/'data'/'catalog.json'; "
                "assert catalog.is_file() and Config.from_env().catalog_path == catalog, catalog; "
                "from app import create_app; client=create_app().test_client(); "
                "assert all(client.get(p).status_code == 200 for p in "
                "['/health', '/', '/static/style.css', '/static/app.js']); "
                "r=client.post('/api/recommendations/preview', json={'roast_level':'light'}); "
                "assert r.status_code == 200 and len(r.json['recommendations']) == 3",
            ],
            env=env,
            cwd=Path(work),
        )


def write_report(path: Path, result: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    # JSON output does not include secrets or user survey records.
    path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"\nReport: {path}", flush=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--offline",
        action="store_true",
        help="Run independent checks without HTTP dependencies; always partial",
    )
    parser.add_argument("--report", type=Path, default=ROOT / ".verification" / "release-report.json")
    args = parser.parse_args()
    state: dict = {
        "schema": 1,
        "source": "scripts/verify_release.py",
        "mode": "offline" if args.offline else "strict",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "stages": [],
        "blockers": [],
        "verdict": "not_started",
    }
    try:
        steps: list[dict] = state["stages"]
        missing_tests = check_required_test_sources(ROOT)
        if missing_tests:
            steps.append(
                {
                    "name": "mandatory_integration_inventory",
                    "status": "failed",
                    "missing_tests": missing_tests,
                }
            )
            state["verdict"] = "failed"
            return 1
        steps.append({"name": "mandatory_integration_inventory", "status": "passed"})
        steps.append(run("compile", [sys.executable, "-m", "compileall", "-q", "app", "tests", "scripts"]))
        cmd = [sys.executable, "-m", "pytest", "-q"]
        for path in BLOCKED_TEST_FILES:
            cmd.append(f"--ignore={path}")
        for path in CORE_MODULES:
            cmd.append(f"--cov={path}")
        cmd.extend(["--cov-report=term-missing", "--cov-fail-under=90"])
        steps.append(run("offline_core", cmd))
        steps.append(build_wheel())
        if any(x["status"] != "passed" for x in steps):
            state["verdict"] = "failed"
            return 1
        if args.offline:
            state["blockers"] = [
                "Offline mode cannot certify Flask, Waitress, Chromium, Ruff or clean HTTP installation."
            ]
            state["verdict"] = "partial_offline_only"
            return 2
        missing = preflight()
        if missing:
            state["blockers"] = missing
            state["verdict"] = "blocked_dependencies"
            print("\nRELEASE BLOCKED:\n" + "\n".join(f" - {s}" for s in missing), file=sys.stderr)
            return 2
        steps.append(run("ruff", [sys.executable, "-m", "ruff", "check", "."]))
        steps.append(run("ruff_format", [sys.executable, "-m", "ruff", "format", "--check", "."]))
        env = {**os.environ, "COFFEE_REQUIRE_BROWSER": "1", "COFFEE_CAPTURE_BROWSER": "1"}
        steps.append(
            run(
                "all_tests_no_skips",
                [
                    sys.executable,
                    "scripts/strict_pytest.py",
                    "--require-integration-tests",
                    "-q",
                    "--cov=app",
                    "--cov-report=term-missing",
                    "--cov-fail-under=80",
                ],
                env=env,
            )
        )
        steps.append(fresh_install_check())
        if any(x["status"] != "passed" for x in steps):
            state["verdict"] = "failed"
            return 1
        state["verdict"] = "local_release_gate_passed"
        return 0
    except Exception as exc:
        state["verdict"] = "failed"
        state["blockers"].append(f"Verifier exception: {type(exc).__name__}: {exc}")
        print(traceback.format_exc(), file=sys.stderr)
        return 1
    finally:
        write_report(args.report, state)
        print(f"VERDICT: {state['verdict'].upper()}", flush=True)


if __name__ == "__main__":
    raise SystemExit(main())
