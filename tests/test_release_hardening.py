"""Verify mandatory integration inventory and immutable CI action references."""

from __future__ import annotations

from pathlib import Path
import re
import subprocess
import sys
from types import SimpleNamespace

from scripts.strict_pytest import (
    REQUIRED_BROWSER_TESTS,
    REQUIRED_SERVER_TESTS,
    StrictCollection,
    check_required_test_sources,
)

ROOT = Path(__file__).resolve().parents[1]


def test_required_suite_identifies_missing_browser_test():
    required = REQUIRED_SERVER_TESTS | REQUIRED_BROWSER_TESTS
    plugin = StrictCollection(required)
    simulated = [SimpleNamespace(nodeid=node) for node in REQUIRED_SERVER_TESTS]
    plugin.pytest_collection_modifyitems(simulated)
    assert plugin.missing_required_tests() == REQUIRED_BROWSER_TESTS


def test_required_suite_recognizes_parameterized_ids():
    required = REQUIRED_SERVER_TESTS | REQUIRED_BROWSER_TESTS
    plugin = StrictCollection(required)
    simulated = [SimpleNamespace(nodeid=node + "[case]") for node in required]
    plugin.pytest_collection_modifyitems(simulated)
    assert plugin.missing_required_tests() == set()


def test_release_runner_fails_when_required_tests_not_collected():
    completed = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "strict_pytest.py"),
            "--require-integration-tests",
            "-q",
            "tests/test_security_config.py",
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
        timeout=90,
    )
    assert completed.returncode != 0
    assert "required integration tests were not collected" in completed.stderr
    assert "tests/test_browser_flow.py::test_real_chromium_form_result_api_and_clipboard" in completed.stderr


def test_ci_requires_server_collection_and_full_release_collection():
    workflow = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
    release = (ROOT / "scripts/verify_release.py").read_text(encoding="utf-8")
    assert "--require-server-tests" in workflow
    assert '"--require-integration-tests"' in release
    for path in ("tests/test_browser_flow.py", "tests/test_live_http.py"):
        assert path in str(REQUIRED_SERVER_TESTS | REQUIRED_BROWSER_TESTS)


def test_ci_pins_all_actions_to_immutable_full_sha():
    workflow = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
    usages = re.findall(r"^\s*- uses:\s*(\S+)", workflow, flags=re.MULTILINE)
    assert len(usages) == 5
    for usage in usages:
        assert re.fullmatch(r"actions/[a-z-]+@[a-f0-9]{40}", usage), usage
    assert "persist-credentials: false" in workflow


def test_mandatory_browser_module_deletion_fails_early(tmp_path):
    # Offline inventory check must reject missing test modules before any
    # package-index or Flask availability checks are attempted.
    for nodeid in REQUIRED_SERVER_TESTS | REQUIRED_BROWSER_TESTS:
        filename, test_name = nodeid.split("::", 1)
        if filename.endswith("test_browser_flow.py"):
            continue
        target = tmp_path / filename
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("a", encoding="utf-8") as handle:
            handle.write(f"def {test_name}():\n    assert True\n")
    missing = check_required_test_sources(tmp_path)
    assert missing == ["tests/test_browser_flow.py::test_real_chromium_form_result_api_and_clipboard"]


def test_mandatory_function_rename_fails_early(tmp_path):
    for nodeid in REQUIRED_SERVER_TESTS | REQUIRED_BROWSER_TESTS:
        filename, test_name = nodeid.split("::", 1)
        target = tmp_path / filename
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("a", encoding="utf-8") as handle:
            handle.write(f"def {test_name}():\n    assert True\n")
    assert not check_required_test_sources(tmp_path)
    browser = tmp_path / "tests/test_browser_flow.py"
    browser.write_text("def test_renamed_browser():\n    assert True\n", encoding="utf-8")
    assert check_required_test_sources(tmp_path) == [
        "tests/test_browser_flow.py::test_real_chromium_form_result_api_and_clipboard"
    ]


def test_release_gate_stops_before_compilation_if_integration_source_missing(monkeypatch, tmp_path):
    from scripts import verify_release as gate

    monkeypatch.setattr(
        gate,
        "check_required_test_sources",
        lambda root: ["tests/test_browser_flow.py::test_real_chromium_form_result_api_and_clipboard"],
    )
    monkeypatch.setattr(
        gate,
        "run",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("Should fail before executing tools")),
    )
    report = tmp_path / "failed-gate.json"
    monkeypatch.setattr(sys, "argv", ["verify_release.py", "--offline", "--report", str(report)])
    assert gate.main() == 1
    import json

    details = json.loads(report.read_text(encoding="utf-8"))
    assert details["verdict"] == "failed"
    assert details["stages"][0]["name"] == "mandatory_integration_inventory"
    assert details["stages"][0]["status"] == "failed"
