import json

import pytest

from tests.project.conftest import RunProject
from tests.project.linting.lint_cases import JAVASCRIPT_MAKEFILE, PACKAGE, STRICT_PRESET


@pytest.mark.parametrize(
    ("files", "configured_path", "limitation"),
    [
        (
            {
                "package.json": PACKAGE,
                "packages/app/package.json": json.dumps({"eslintConfig": {"extends": [STRICT_PRESET]}}),
                "Makefile": JAVASCRIPT_MAKEFILE,
            },
            "packages/app/package.json",
            "uses a configuration location pristine does not statically support",
        ),
        (
            {
                "package.json": PACKAGE,
                ".eslintrc.js": "module.exports = {};\n",
                "Makefile": JAVASCRIPT_MAKEFILE,
            },
            ".eslintrc.js",
            "uses a configuration mode pristine does not statically support",
        ),
    ],
)
def test_eslint_names_the_actual_unverifiable_configuration(
    run_project: RunProject, files: dict[str, str], configured_path: str, limitation: str
) -> None:
    _, report = run_project(files)
    finding = next(finding for finding in report["findings"] if finding["check_id"] == "PROJ-3")
    assert finding.get("kind", "code") == "verification"
    assert finding["path"].endswith(configured_path)
    assert finding["message"] == (
        f"cannot verify that the ESLint rule sets are configured: {configured_path} {limitation}"
    )
