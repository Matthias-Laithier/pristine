import json
from collections.abc import Mapping

from tests.project.conftest import RunProject, rule_findings
from tests.project.quality_manifests import PYTHON_SOURCE

PYTHON_PROJECT = (
    '[project]\nname = "app"\nrequires-python = ">=3.13"\n\n[dependency-groups]\ndev = ["ruff>=0.6", "mypy>=1.0"]\n'
)
PYTHON_MAKEFILE = (
    "dev:\n\t./run\ncheck:\n\truff check .\n\truff format --check .\n\tmypy --strict .\n\tvulture .\ncheck-all: check\n"
)
PACKAGE = json.dumps(
    {
        "engines": {"node": ">=22"},
        "dependencies": {"react": "19"},
        "devDependencies": {"eslint": "9", "prettier": "3", "typescript": "5"},
        "scripts": {"check": "eslint . && prettier --check . && tsc --noEmit && knip"},
    }
)
JAVASCRIPT_MAKEFILE = "dev:\n\tnpm start\ncheck:\n\tnpm run check\ncheck-all: check\n"
ANY_RULE = "@typescript-eslint/no-explicit-any"
STRICT_PRESET = "plugin:@typescript-eslint/strict-type-checked"
REACT_PRESETS = ["plugin:react-hooks/recommended", "plugin:jsx-a11y/recommended"]
BASE_PRESET_RULES = (
    "@typescript-eslint/no-floating-promises",
    "@typescript-eslint/no-explicit-any",
)


def lint_messages(files: dict[str, str], run_project: RunProject) -> list[str]:
    _, report = run_project(files)
    return [message for _, message, _ in rule_findings(report, "TL-3")]


def eslint_config(extends: list[str], rules: Mapping[str, object] = {}) -> str:
    return json.dumps({"extends": extends, "rules": rules})


def with_python_lint_config(config: str, extra: dict[str, str] | None = None) -> dict[str, str]:
    return {**PYTHON_SOURCE, "pyproject.toml": PYTHON_PROJECT + config, "Makefile": PYTHON_MAKEFILE, **(extra or {})}


def with_typescript_config(config: str) -> dict[str, str]:
    return {"package.json": PACKAGE, ".eslintrc.json": config, "Makefile": JAVASCRIPT_MAKEFILE}
