import json
from pathlib import Path

import pytest

from tests.conftest import json_list, json_object


@pytest.fixture
def vulnerable_output() -> str:
    return (Path(__file__).parents[2] / "assets/audit/vulnerable.json").read_text(encoding="utf-8")


@pytest.fixture
def clean_output() -> str:
    return (Path(__file__).parents[2] / "assets/audit/clean.json").read_text(encoding="utf-8")


@pytest.fixture
def native_package(vulnerable_output: str) -> dict[str, object]:
    document = json_object(json.loads(vulnerable_output))
    result = json_object(json_list(document["results"])[0])
    return json_object(json_list(result["packages"])[1])


def native_output(packages: list[object], **extra: object) -> str:
    return json.dumps(
        {
            "results": [{"source": {"path": "/fixtures/vulnerable/uv.lock", "type": "lockfile"}, "packages": packages}],
            **extra,
        }
    )
