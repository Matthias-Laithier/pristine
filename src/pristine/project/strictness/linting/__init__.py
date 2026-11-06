from pristine.project.strictness.linting.ruff import ruff_shortfall
from pristine.project.strictness.linting.typescript import eslint_shortfall

LINT_CHECKS = (ruff_shortfall, eslint_shortfall)

__all__ = ("LINT_CHECKS",)
