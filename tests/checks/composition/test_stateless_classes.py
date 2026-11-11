import pytest

from tests.conftest import RunPristine, rule_findings

CHECK_ID = "DEP-2"
NAMESPACE = """class PriceMath:
    \"\"\"Price helpers.\"\"\"

    @staticmethod
    def line_total(unit_price, quantity):
        return unit_price * quantity

    @classmethod
    def _discounted(cls, total, rate):
        return total * (1 - rate)


TOTAL = PriceMath.line_total(3, 4)
"""
FLAGGED = [
    NAMESPACE,
    "class Names:\n    @staticmethod\n    def full(given):\n        return given\n\n\n__all__ = ['Names']\n",
    "class Names:\n    @staticmethod\n    def full(given, family):\n        pass\n        return given + family\n",
    "class BaseNames:\n    @staticmethod\n    def full(given):\n        return given\n",
    "class NamesMixin:\n    @staticmethod\n    def full(given):\n        return given\n",
]
KEPT = {
    "base class": "class Names(Formatter):\n    @staticmethod\n    def full(given):\n        return given\n",
    "generic class": "class Names[T]:\n    @staticmethod\n    def full(given):\n        return given\n",
    "decorated class": "@dataclass\nclass Names:\n    @staticmethod\n    def full(given):\n        return given\n",
    "metaclass": "class Names(metaclass=Registry):\n    @staticmethod\n    def full(given):\n        return given\n",
    "attribute": "class Names:\n    SEPARATOR = ' '\n\n    @staticmethod\n    def full(given):\n        return given\n",
    "dunder method": "class Names:\n    def __call__(self, given):\n        return given\n",
    "instance method": "class Names:\n    def full(self, given):\n        return given\n",
    "receiver use": "class Names:\n    @classmethod\n    def full(cls, given):\n        return cls.SEP.join(given)\n",
    "missing receiver": "class Names:\n    @classmethod\n    def full():\n        return 'a'\n",
    "other decorator": "class Names:\n    @property\n    def full(self):\n        return 'a'\n",
    "stub method": "class Names:\n    @staticmethod\n    def full(given):\n        raise NotImplementedError\n",
    "ellipsis stub": "class Names:\n    @staticmethod\n    def full(given):\n        ...\n",
    "no method": "class Names:\n    pass\n",
    "nested class": "class Names:\n    class Meta:\n        @staticmethod\n        def full(given):\n            return given\n",
    "extended": "class Names:\n    @staticmethod\n    def full(given):\n        return given\n\n\nclass Short(Names):\n    pass\n",
    "instantiated": "class Names:\n    @staticmethod\n    def full(given):\n        return given\n\n\nNAMES = Names()\n",
    "passed": "class Names:\n    @staticmethod\n    def full(given):\n        return given\n\n\nregister(Names)\n",
    "public vocabulary": "class Goal:\n    @staticmethod\n    def gte(value):\n        return value\n\n    @staticmethod\n    def lte(value):\n        return value\n",
    "named in a string": "class Names:\n    @staticmethod\n    def full(given):\n        return given\n\n\nPATH = 'names.Names.full'\n",
    "inner class": "def build():\n    class Names:\n        @staticmethod\n        def full(given):\n            return given\n",
}
TEST_CLASS = "class TestNames:\n    @staticmethod\n    def test_full():\n        assert full('a') == 'a'\n"


@pytest.mark.parametrize("source", FLAGGED)
def test_namespace_class_is_a_warning(run_pristine: RunPristine, source: str) -> None:
    _, report = run_pristine({"names.py": source})
    assert rule_findings(report, CHECK_ID) == [(1, "warning")]


@pytest.mark.parametrize("source", KEPT.values(), ids=KEPT.keys())
def test_class_with_a_reason_is_kept(run_pristine: RunPristine, source: str) -> None:
    _, report = run_pristine({"names.py": source})
    assert rule_findings(report, CHECK_ID) == []


def test_pytest_class_in_a_test_file_is_kept(run_pristine: RunPristine) -> None:
    _, report = run_pristine({"test_names.py": TEST_CLASS})
    assert rule_findings(report, CHECK_ID) == []


def test_test_named_class_outside_tests_is_reported(run_pristine: RunPristine) -> None:
    _, report = run_pristine({"names.py": TEST_CLASS})
    assert rule_findings(report, CHECK_ID) == [(1, "warning")]
