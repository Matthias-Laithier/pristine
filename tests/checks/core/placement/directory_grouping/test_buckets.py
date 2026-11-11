import pytest

from tests.conftest import RunPristine, rule_findings

RULE_ID = "CR-15"
CODE = "VALUE = 1\n"
WARNING = [(1, "warning")]


def tree(folder: str, names: list[str]) -> dict[str, str]:
    return {f"{folder}/{name}": CODE for name in names}


@pytest.mark.parametrize("bucket", ["common", "misc", "helpers", "utils", "util"])
def test_vague_bucket_is_reported_once(run_pristine: RunPristine, bucket: str) -> None:
    _, report = run_pristine(tree(f"billing/src/{bucket}", ["dates.py", "money.py"]))
    assert rule_findings(report, RULE_ID) == WARNING


@pytest.mark.parametrize(
    "folder",
    [
        "billing/src/pricing",
        "billing/node_modules/acme/utils",
        "billing/tests/helpers",
    ],
)
def test_named_vendored_and_test_folders_are_not_buckets(run_pristine: RunPristine, folder: str) -> None:
    _, report = run_pristine(tree(folder, ["dates.py", "money.py"]))
    assert rule_findings(report, RULE_ID) == []


def test_bucket_of_data_files_is_not_reported(run_pristine: RunPristine) -> None:
    _, report = run_pristine({"billing/src/common/rates.json": "{}\n", "billing/src/common/README.md": "# Rates\n"})
    assert rule_findings(report, RULE_ID) == []
