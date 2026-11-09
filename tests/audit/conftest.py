import json

import pytest

from tests.conftest import audit_recording, json_list, json_object


@pytest.fixture
def vulnerable_output() -> str:
    return audit_recording("vulnerable")


@pytest.fixture
def clean_output() -> str:
    return audit_recording("clean")


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
