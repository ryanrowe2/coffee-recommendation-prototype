"""Run pytest with no skips and an optional mandatory integration-test inventory.

`--require-server-tests` is used in the CI matrix without a browser.
`--require-integration-tests` also requires the real Chromium journey and is
mandatory for the full local release gate. Ordinary focused pytest invocations
can still run without either inventory option.
"""

from __future__ import annotations

import ast
from pathlib import Path
import sys

import pytest


REQUIRED_SERVER_TESTS = frozenset(
    {
        "tests/test_flask_endpoints.py::test_end_to_end_form_to_results_and_api",
        "tests/test_flask_endpoints.py::test_signed_webhook_idempotent",
        "tests/test_live_http.py::test_actual_loopback_http_flow",
        "tests/test_runtime_certification.py::test_documented_servers_complete_http_workflow",
        "tests/test_waitress_entrypoint.py::test_waitress_subprocess_starts_and_serves_http",
    }
)
REQUIRED_BROWSER_TESTS = frozenset(
    {"tests/test_browser_flow.py::test_real_chromium_form_result_api_and_clipboard"}
)


def check_required_test_sources(root: Path) -> list[str]:
    """Fail early if a mandatory test file/function disappears or is renamed.

    This static guard runs even in offline mode; StrictCollection separately
    confirms that these tests are actually *collected* in the full runtime.
    """
    missing: list[str] = []
    for nodeid in sorted(REQUIRED_SERVER_TESTS | REQUIRED_BROWSER_TESTS):
        rel_path, function_name = nodeid.split("::", 1)
        path = root / rel_path
        if not path.is_file():
            missing.append(nodeid)
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except (OSError, SyntaxError, UnicodeError):
            missing.append(nodeid)
            continue
        top_level = {
            node.name for node in tree.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        }
        if function_name not in top_level:
            missing.append(nodeid)
    return missing


class StrictCollection:
    def __init__(self, required_tests: frozenset[str] = frozenset()) -> None:
        self.skips: list[str] = []
        self.required_tests = required_tests
        self.collected: set[str] = set()

    @staticmethod
    def canonical_test_id(nodeid: str) -> str:
        # Parametrized tests have suffixed [case-name] node IDs.
        return nodeid.split("[", 1)[0].replace("\\", "/")

    def missing_required_tests(self) -> set[str]:
        return set(self.required_tests) - self.collected

    def pytest_collection_modifyitems(self, items: list[pytest.Item]) -> None:
        # Called after pytest's deselection: skipped/ignored/deselected tests
        # cannot satisfy the mandatory inventory.
        self.collected = {self.canonical_test_id(item.nodeid) for item in items}

    def pytest_collectreport(self, report: pytest.CollectReport) -> None:
        if report.skipped:
            self.skips.append(f"collection: {report.nodeid}")

    def pytest_runtest_logreport(self, report: pytest.TestReport) -> None:
        if report.skipped:
            self.skips.append(f"test: {report.nodeid}")

    def pytest_sessionfinish(self, session: pytest.Session, exitstatus: int) -> None:
        missing = self.missing_required_tests()
        if self.skips or missing:
            session.exitstatus = pytest.ExitCode.TESTS_FAILED
        if self.skips:
            print(f"\nSTRICT FAILURE: {len(self.skips)} skipped tests or modules:", file=sys.stderr)
            for name in self.skips:
                print(f"  - {name}", file=sys.stderr)
        if missing:
            print("\nSTRICT FAILURE: required integration tests were not collected:", file=sys.stderr)
            for test_id in sorted(missing):
                print(f"  - {test_id}", file=sys.stderr)


def main() -> int:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    argv = sys.argv[1:]
    require_all = "--require-integration-tests" in argv
    require_server = "--require-server-tests" in argv
    if require_all and require_server:
        print("Specify only one required-test inventory mode.", file=sys.stderr)
        return 2
    argv = [arg for arg in argv if arg not in ("--require-integration-tests", "--require-server-tests")]
    required = REQUIRED_SERVER_TESTS if require_server else frozenset()
    if require_all:
        required = REQUIRED_SERVER_TESTS | REQUIRED_BROWSER_TESTS
    return int(pytest.main(argv, plugins=[StrictCollection(required)]))


if __name__ == "__main__":
    raise SystemExit(main())
