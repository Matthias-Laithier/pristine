import pytest

from pristine.registration import registering


def test_registering_rejects_a_key_already_taken() -> None:
    registry: dict[str, str] = {}
    registering(registry, "python", "go")("python and go handler")
    with pytest.raises(ValueError, match="go"):
        registering(registry, "javascript", "go")("second go handler")
    assert registry == {"python": "python and go handler", "go": "python and go handler"}
