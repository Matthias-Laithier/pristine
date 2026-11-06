import json

PACKAGE = {
    "engines": {"node": ">=22"},
    "devDependencies": {"eslint": "9", "prettier": "3", "typescript": "5"},
    "scripts": {"lint": "eslint . && prettier --check .", "typecheck": "tsc --noEmit", "verify": "npm run lint"},
}
ESLINT_CONFIG = json.dumps({"extends": ["plugin:@typescript-eslint/strict-type-checked"]})
