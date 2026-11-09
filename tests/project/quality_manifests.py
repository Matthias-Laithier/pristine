import json

PYTHON_SOURCE = {"src/invoices.py": "sum([1, 2])\n"}

PACKAGE = {
    "engines": {"node": ">=22"},
    "devDependencies": {"eslint": "9", "prettier": "3", "typescript": "5"},
    "scripts": {
        "lint": "eslint . && prettier --check . && knip",
        "typecheck": "tsc --noEmit",
        "verify": "npm run lint",
        "audit": "npm audit",
    },
}
ESLINT_CONFIG = json.dumps({"extends": ["plugin:@typescript-eslint/strict-type-checked"]})
