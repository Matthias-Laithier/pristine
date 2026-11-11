import json
from collections.abc import Mapping

from tests.project.conftest import RunProject, rule_findings

PYTHON_PROJECT = (
    '[project]\nname = "app"\nrequires-python = ">=3.13"\n\n[dependency-groups]\ndev = ["ruff>=0.6", "mypy>=1.0"]\n'
)
PYTHON_MAKEFILE = (
    "dev:\n\t./run\ncheck:\n\truff check .\n\truff format --check .\n\tmypy --strict .\ncheck-all: check\n"
)
PACKAGE = json.dumps(
    {
        "engines": {"node": ">=22"},
        "dependencies": {"react": "19"},
        "devDependencies": {"eslint": "9", "prettier": "3", "typescript": "5"},
        "scripts": {"check": "eslint . && prettier --check . && tsc --noEmit"},
    }
)
JAVASCRIPT_MAKEFILE = "dev:\n\tnpm start\ncheck:\n\tnpm run check\ncheck-all: check\n"
ANY_RULE = "@typescript-eslint/no-explicit-any"
STRICT_PRESET = "plugin:@typescript-eslint/strict-type-checked"
REACT_PRESETS = ["plugin:react-hooks/recommended", "plugin:jsx-a11y/recommended"]
ANNOTATIONS = '[tool.ruff.lint]\nextend-select = ["S", "ASYNC", "DTZ", "G", "T20", "FBT", "BLE", "ARG", "ERA", "ANN"]\n'
ANNOTATIONS_MAKEFILE = (
    "dev:\n\t./run\ncheck:\n\truff check .\n\truff format --check .\n\tty check .\ncheck-all: check\n"
)
BASE_PRESET_RULES = (
    "@typescript-eslint/no-floating-promises",
    "@typescript-eslint/no-explicit-any",
)


def lint_messages(files: dict[str, str], run_project: RunProject) -> list[str]:
    _, report = run_project(files)
    return [message for _, message, _ in rule_findings(report, "PROJ-3")]


def annotation_findings(files: dict[str, str], run_project: RunProject) -> list[tuple[str, str]]:
    _, report = run_project(files)
    return [
        (finding["severity"], finding.get("kind", "rule"))
        for finding in report["findings"]
        if "explicit Python annotations" in finding["message"]
    ]


def eslint_config(extends: list[str], rules: Mapping[str, object] = {}) -> str:
    return json.dumps({"extends": extends, "rules": rules})


def with_python_lint_config(config: str, extra: dict[str, str] | None = None) -> dict[str, str]:
    return {"pyproject.toml": PYTHON_PROJECT + config, "Makefile": PYTHON_MAKEFILE, **(extra or {})}


def with_typescript_config(config: str) -> dict[str, str]:
    return {"package.json": PACKAGE, ".eslintrc.json": config, "Makefile": JAVASCRIPT_MAKEFILE}
