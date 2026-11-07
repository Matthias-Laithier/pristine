import json
import subprocess
import sys
from pathlib import Path


def test_rules_metadata_does_not_import_native_parsers() -> None:
    observer = r"""
import json
import sys

native_imports = []


def observe_import(event, args):
    if event == "import" and args[0].partition(".")[0] in {"tree_sitter", "tree_sitter_language_pack"}:
        native_imports.append(args[0])


sys.addaudithook(observe_import)
from pristine.cli.main import main

exit_code = main(["rules", "--json"])
print(json.dumps({"exit_code": exit_code, "native_imports": native_imports}), file=sys.stderr)
"""
    result = subprocess.run(
        [sys.executable, "-c", observer],
        capture_output=True,
        env={"PYTHONPATH": str(Path(__file__).parents[2] / "src")},
        text=True,
        timeout=30,
        check=False,
    )
    assert result.returncode == 0
    assert result.stdout.startswith('[\n  {\n    "rule_id": "BS-1",')
    assert json.loads(result.stderr) == {"exit_code": 0, "native_imports": []}
