from pristine.project.gates.audits import CHECKS as AUDIT_CHECKS
from pristine.project.gates.contract import CHECKS as CONTRACT_CHECKS

CHECKS = (*CONTRACT_CHECKS, *AUDIT_CHECKS)

__all__ = ["CHECKS"]
