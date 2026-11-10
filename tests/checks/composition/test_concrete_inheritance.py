import pytest

from tests.conftest import RunPristine, rule_findings

RULE_ID = "CO-1"
STORAGE = """class FileStorage:
    def __init__(self, root):
        self.root = root

    def save(self, name, data):
        path = self.root / name
        path.write_bytes(data)
"""
VARIANT = (
    "\n\nclass EncryptedFileStorage(FileStorage):\n    def save(self, name, data):\n        super().save(name, data)\n"
)
KEPT = {
    "no override": STORAGE + "\n\nclass NamedStorage(FileStorage):\n    def rename(self, name):\n        return name\n",
    "dunder override": STORAGE
    + "\n\nclass Storage(FileStorage):\n    def __init__(self):\n        super().__init__(1)\n",
    "based base": STORAGE.replace("FileStorage:", "FileStorage(Store):") + VARIANT,
    "generic base": STORAGE.replace("FileStorage:", "FileStorage[T]:") + VARIANT,
    "decorated base": "@dataclass\n" + STORAGE + VARIANT,
    "stub method": STORAGE + "\n    def load(self, name):\n        raise NotImplementedError\n" + VARIANT,
    "one-line method": STORAGE.replace("        path = self.root / name\n", "") + VARIANT,
    "abstract method": STORAGE.replace("    def save", "    @abstractmethod\n    def save") + VARIANT,
    "extension name": STORAGE.replace("FileStorage", "BaseStorage") + VARIANT.replace("FileStorage", "BaseStorage"),
    "private base": STORAGE.replace("FileStorage", "_Storage") + VARIANT.replace("FileStorage", "_Storage"),
    "several variants": STORAGE + VARIANT + VARIANT.replace("EncryptedFileStorage", "ZippedFileStorage"),
    "several bases": STORAGE + VARIANT.replace("(FileStorage)", "(FileStorage, Audited)"),
    "imported base": "from storage import FileStorage\n" + VARIANT,
}


def test_variant_of_a_concrete_class_is_a_warning(run_pristine: RunPristine) -> None:
    _, report = run_pristine({"storage.py": STORAGE + VARIANT})
    assert rule_findings(report, RULE_ID) == [(10, "warning")]


@pytest.mark.parametrize("source", KEPT.values(), ids=KEPT.keys())
def test_designed_extension_is_kept(run_pristine: RunPristine, source: str) -> None:
    _, report = run_pristine({"storage.py": source})
    assert rule_findings(report, RULE_ID) == []


def test_test_files_are_kept(run_pristine: RunPristine) -> None:
    _, report = run_pristine({"tests/storage.py": STORAGE + VARIANT})
    assert rule_findings(report, RULE_ID) == []
