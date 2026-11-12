"""Prevent the release workflow from silently accepting omitted tests."""

from __future__ import annotations

from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / "scripts" / "strict_pytest.py"


def test_strict_pytest_rejects_module_skip(tmp_path):
    test_file = tmp_path / "test_dep.py"
    test_file.write_text('import pytest\npytest.skip("Dependency unavailable", allow_module_level=True)\n')
    completed = subprocess.run(
        [sys.executable, str(RUNNER), "-q", str(test_file)],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert completed.returncode != 0
    assert "STRICT FAILURE" in completed.stderr
    assert "collection" in completed.stderr


def test_strict_pytest_rejects_skipped_test(tmp_path):
    test_file = tmp_path / "test_feature.py"
    test_file.write_text(
        'import pytest\n@pytest.mark.skip(reason="Unverified")\ndef test_feature():\n    assert True\n'
    )
    completed = subprocess.run(
        [sys.executable, str(RUNNER), "-q", str(test_file)],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert completed.returncode != 0
    assert "STRICT FAILURE" in completed.stderr
    assert "test:" in completed.stderr


def test_strict_pytest_accepts_actual_pass(tmp_path):
    test_file = tmp_path / "test_good.py"
    test_file.write_text("def test_actual():\n    assert 2 + 2 == 4\n")
    completed = subprocess.run(
        [sys.executable, str(RUNNER), "-q", str(test_file)],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr


def test_strict_runner_imports_repository_scripts(tmp_path):
    test_file = tmp_path / "test_repository_import.py"
    test_file.write_text(
        "from scripts.send_mock_webhook import validate_mock_url\ndef test_import():\n    assert callable(validate_mock_url)\n"
    )
    completed = subprocess.run(
        [sys.executable, str(RUNNER), "-q", str(test_file)],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr


def test_release_gate_rejects_format_failure(monkeypatch, tmp_path):
    from scripts import verify_release as gate

    report = tmp_path / "report.json"
    monkeypatch.setattr(sys, "argv", ["verify_release.py", "--report", str(report)])
    monkeypatch.setattr(gate, "preflight", lambda: [])
    monkeypatch.setattr(gate, "build_wheel", lambda: {"name": "wheel_content", "status": "passed"})
    monkeypatch.setattr(gate, "fresh_install_check", lambda: {"name": "fresh_health", "status": "passed"})

    def run(name, cmd, **kwargs):
        return {"name": name, "status": "failed" if name == "ruff_format" else "passed"}

    monkeypatch.setattr(gate, "run", run)
    assert gate.main() == 1
    import json

    assert json.loads(report.read_text())["verdict"] == "failed"


def test_clean_install_installs_wheel_outside_checkout(monkeypatch):
    from scripts import verify_release as gate

    calls = []

    def run(name, cmd, **kwargs):
        calls.append((name, cmd, kwargs))
        if name == "fresh_wheel_build":
            dest = Path(cmd[cmd.index("--outdir") + 1])
            dest.mkdir()
            (dest / "coffee_test.whl").write_bytes(b"test fixture only")
        return {"name": name, "status": "passed"}

    monkeypatch.setattr(gate, "run", run)
    assert gate.fresh_install_check()["status"] == "passed"
    install = next(cmd for name, cmd, _ in calls if name == "fresh_install")
    assert install[-1].endswith(".whl")
    health = next(kwargs for name, _, kwargs in calls if name == "fresh_health")
    assert health["cwd"] != ROOT
    assert "PYTHONPATH" not in health["env"]


def test_wheel_gate_rejects_nonreproducible_bytes(monkeypatch):
    from scripts import verify_release as gate

    def run(name, cmd, **kwargs):
        dest = Path(cmd[cmd.index("--wheel-dir") + 1])
        dest.mkdir(exist_ok=True)
        (dest / "coffee_recommendation_prototype-test.whl").write_bytes(name.encode())
        return {"name": name, "status": "passed"}

    monkeypatch.setattr(gate, "run", run)
    assert gate.build_wheel()["name"] == "wheel_reproducibility"
    assert gate.build_wheel()["status"] == "failed"
