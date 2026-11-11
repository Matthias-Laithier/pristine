import json

import pytest

from tests.project.conftest import RunProject
from tests.project.linting.lint_cases import (
    ANY_RULE,
    BASE_PRESET_RULES,
    PACKAGE,
    REACT_PRESETS,
    STRICT_PRESET,
    eslint_config,
    lint_messages,
    with_typescript_config,
)


def test_eslint_requires_the_actual_strict_preset(run_project: RunProject) -> None:
    files = with_typescript_config(eslint_config([*REACT_PRESETS, STRICT_PRESET]))
    assert lint_messages(files, run_project) == []


def test_eslint_rejects_missing_react_rule_sets(run_project: RunProject) -> None:
    files = with_typescript_config(eslint_config([STRICT_PRESET]))
    assert lint_messages(files, run_project) == [
        (
            "ESLint does not enable the required rule sets (react-hooks, jsx-a11y); enable "
            "@typescript-eslint/strict-type-checked, no-floating-promises, and no-explicit-any "
            "(plus react-hooks and jsx-a11y in React projects)"
        )
    ]


def test_eslint_rejects_boolean_rule_severities(run_project: RunProject) -> None:
    files = with_typescript_config(eslint_config([STRICT_PRESET], {ANY_RULE: True}))
    assert lint_messages(files, run_project) == [
        (
            "ESLint does not enable the required rule sets (@typescript-eslint/no-explicit-any, react-hooks, "
            "jsx-a11y); enable @typescript-eslint/strict-type-checked, no-floating-promises, and no-explicit-any "
            "(plus react-hooks and jsx-a11y in React projects)"
        )
    ]


def test_eslint_checks_package_config_without_the_dependency(run_project: RunProject) -> None:
    package = json.loads(PACKAGE)
    del package["devDependencies"]["eslint"]
    del package["dependencies"]["react"]
    package["eslintConfig"] = {
        "extends": [STRICT_PRESET],
        "rules": {ANY_RULE: "off", "react-hooks/rules-of-hooks": "off", "jsx-a11y/alt-text": "off"},
    }
    makefile = (
        'dev:\n\tnpm start\ncheck:\n\ttest -z "$$(prettier --check .)"\n\teslint .\n\ttsc --noEmit\ncheck-all: check\n'
    )
    files = {
        "package.json": json.dumps(package),
        "Makefile": makefile,
        "tsconfig.json": json.dumps({"compilerOptions": {"strict": True}}),
    }
    assert lint_messages(files, run_project) == [
        (
            "ESLint does not enable the required rule sets (@typescript-eslint/no-explicit-any); enable "
            "@typescript-eslint/strict-type-checked, no-floating-promises, and no-explicit-any "
            "(plus react-hooks and jsx-a11y in React projects)"
        )
    ]


def test_eslint_flat_config_is_explicitly_unverifiable(run_project: RunProject) -> None:
    files = {
        **with_typescript_config(eslint_config([STRICT_PRESET], {ANY_RULE: "error"})),
        "eslint.config.json": "",
    }
    _, report = run_project(files)
    finding = next(finding for finding in report["findings"] if finding["check_id"] == "PROJ-3")
    assert finding["kind"] == "verification"
    assert finding["message"] == (
        "cannot verify that the ESLint rule sets are configured: eslint.config.json uses a configuration mode "
        "pristine does not statically support"
    )


@pytest.mark.parametrize(
    ("files", "expected"),
    [
        (
            with_typescript_config(eslint_config([STRICT_PRESET], {ANY_RULE: [0, {"fixToNull": True}]})),
            [
                (
                    "ESLint does not enable the required rule sets (@typescript-eslint/no-explicit-any, react-hooks, jsx-a11y); "
                    "enable @typescript-eslint/strict-type-checked, no-floating-promises, and no-explicit-any "
                    "(plus react-hooks and jsx-a11y in React projects)"
                )
            ],
        ),
        (
            with_typescript_config(eslint_config([STRICT_PRESET, REACT_PRESETS[0]])),
            [
                (
                    "ESLint does not enable the required rule sets (jsx-a11y); enable @typescript-eslint/strict-type-checked, "
                    "no-floating-promises, and no-explicit-any (plus react-hooks and jsx-a11y in React projects)"
                )
            ],
        ),
        (
            with_typescript_config(eslint_config([], {rule: "error" for rule in BASE_PRESET_RULES})),
            [
                (
                    "cannot verify that the ESLint rule sets are configured: the explicit rules do not prove the "
                    "@typescript-eslint/strict-type-checked preset"
                )
            ],
        ),
        (
            with_typescript_config(
                eslint_config([STRICT_PRESET, *REACT_PRESETS], {ANY_RULE: ["error", {"fixToNull": True}]})
            ),
            [],
        ),
        (
            {
                **with_typescript_config(eslint_config([STRICT_PRESET, *REACT_PRESETS])),
                "eslint.config.js": "export default []\n",
            },
            [
                (
                    "cannot verify that the ESLint rule sets are configured: eslint.config.js uses a configuration mode "
                    "pristine does not statically support"
                )
            ],
        ),
    ],
)
def test_eslint_rule_proofs(run_project: RunProject, files: dict[str, str], expected: list[str]) -> None:
    assert lint_messages(files, run_project) == expected
