import importlib
import os
from pathlib import Path

import pytest

from pristine.checks.definitions import FileCheck
from pristine.engine import inspection
from pristine.engine.read_digests import read_digest
from pristine.reports.findings import Finding
from pristine.reports.outcomes import Checked
from pristine.syntax.parsing import ParsedFile
from tests.services.outcome_cache.conftest import write

NEIGHBOR = "neighbor.cfg"


def test_reads_made_by_imports_are_not_recorded(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    write(tmp_path, {"app.py": "VALUE = 1\n", "late_module.py": "FLAG = 1\n"})
    monkeypatch.syspath_prepend(str(tmp_path))

    def importing(parsed: ParsedFile) -> list[Finding]:
        del parsed
        assert importlib.import_module("late_module").FLAG == 1
        return []

    monkeypatch.setattr(inspection, "file_checks", lambda: [FileCheck("TEST-9", "Import", "Imports.", importing)])
    outcome = inspection.inspect_file("app.py")
    assert isinstance(outcome, Checked)
    assert outcome.reads == {}


def test_a_read_through_an_open_descriptor_is_untraceable(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    write(tmp_path, {"app.py": "VALUE = 1\n"})
    descriptor = os.open(tmp_path, os.O_RDONLY)

    def by_descriptor(parsed: ParsedFile) -> list[Finding]:
        del parsed
        os.stat(descriptor)
        return []

    monkeypatch.setattr(inspection, "file_checks", lambda: [FileCheck("TEST-9", "Fd", "Stats an fd.", by_descriptor)])
    try:
        outcome = inspection.inspect_file("app.py")
    finally:
        os.close(descriptor)
    assert isinstance(outcome, Checked)
    assert outcome.reads is None


def test_read_digests_distinguish_absence_content_and_listings(tmp_path: Path) -> None:
    target = str(tmp_path / NEIGHBOR)
    absent = read_digest(target, listed=False)
    write(tmp_path, {NEIGHBOR: "a\n"})
    first = read_digest(target, listed=False)
    write(tmp_path, {NEIGHBOR: "b\n"})
    listing = read_digest(str(tmp_path), listed=True)
    write(tmp_path, {"added.txt": ""})
    assert len({absent, first, read_digest(target, listed=False)}) == 3
    assert read_digest(str(tmp_path), listed=False) == read_digest(str(tmp_path), listed=False)
    assert read_digest(str(tmp_path), listed=True) != listing
