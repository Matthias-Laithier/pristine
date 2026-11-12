import json
import os
from collections.abc import Iterator
from pathlib import Path

import pytest

from pristine.reports.findings import Finding, Severity, finding_record
from pristine.reports.outcomes import Checked, Outcome, Skipped, Unchecked, Unsupported
from pristine.services.outcome_cache import OutcomeCache
from pristine.services.outcome_cache.files import prepared_store
from pristine.services.outcome_cache.inputs import FileInputs
from pristine.services.outcome_cache.store import SEAL_SEPARATOR

SECRET = bytes(range(32))
FINDING = Finding("app.py", 1, "STR-1", Severity.ERROR, "too long")


def opened(root: Path, secret: bytes = SECRET) -> OutcomeCache:
    return OutcomeCache(prepared_store(root / "cache", "outcomes-test"), FileInputs(str(root)), secret)


def stored(root: Path, outcomes: dict[str, Outcome], secret: bytes = SECRET) -> OutcomeCache:
    cache = opened(root, secret)
    _, misses = cache.lookup(sorted(outcomes))
    list(cache.recorded(iter([(path, outcomes[path]) for path in misses])))
    return cache


def reused(root: Path, paths: list[str], secret: bytes = SECRET) -> dict[str, Outcome]:
    hits, _ = opened(root, secret).lookup(paths)
    return hits


@pytest.fixture
def project(tmp_path: Path) -> Path:
    (tmp_path / "app.py").write_text("VALUE = 1\n")
    (tmp_path / "notes.md").write_text("notes\n")
    (tmp_path / "data.bin").write_text("binary\n")
    return tmp_path


def test_deterministic_outcomes_are_reused(project: Path) -> None:
    outcomes: dict[str, Outcome] = {
        "app.py": Checked([FINDING]),
        "notes.md": Skipped("prose or data file, exempt from these checks"),
        "data.bin": Unsupported("no grammar for this file type"),
    }
    stored(project, outcomes)
    assert reused(project, sorted(outcomes)) == outcomes


def test_crashes_and_timeouts_are_never_reused(project: Path) -> None:
    stored(project, {"app.py": Unchecked("the parser crashed or timed out on this file")})
    assert reused(project, ["app.py"]) == {}


def test_a_result_for_content_edited_during_the_check_is_not_reused_after_a_revert(project: Path) -> None:
    cache = opened(project)
    cache.lookup(["app.py"])

    def edited_during_check() -> Iterator[tuple[str, Outcome]]:
        (project / "app.py").write_text("VALUE = 22\n")
        yield "app.py", Checked([FINDING])

    list(cache.recorded(edited_during_check()))
    (project / "app.py").write_text("VALUE = 1\n")
    assert reused(project, ["app.py"]) == {}


def test_a_result_for_a_manifest_added_during_the_check_is_not_reused_after_its_removal(project: Path) -> None:
    cache = opened(project)
    cache.lookup(["app.py"])

    def manifest_added() -> Iterator[tuple[str, Outcome]]:
        (project / "pyproject.toml").write_text("[project]\n")
        yield "app.py", Checked([])

    list(cache.recorded(manifest_added()))
    (project / "pyproject.toml").unlink()
    assert reused(project, ["app.py"]) == {}


def test_entries_of_files_outside_this_run_are_kept(project: Path) -> None:
    stored(project, {"app.py": Checked([]), "notes.md": Skipped("prose")})
    stored(project, {"app.py": Checked([])})
    assert reused(project, ["notes.md"]) == {"notes.md": Skipped("prose")}


def test_entries_of_deleted_files_are_pruned(project: Path) -> None:
    stored(project, {"app.py": Checked([]), "notes.md": Skipped("prose")})
    (project / "notes.md").unlink()
    stored(project, {"app.py": Checked([])})
    (project / "notes.md").write_text("notes\n")
    assert reused(project, ["notes.md"]) == {}


def store_file(project: Path) -> Path:
    return project / "cache" / "outcomes-test"


@pytest.mark.parametrize(
    "corruption",
    [b"", b"not sealed", b"\x00" * 64, b"seal\n{}"],
    ids=["empty", "unsealed", "binary", "wrong-seal"],
)
def test_a_corrupt_store_is_a_miss(project: Path, corruption: bytes) -> None:
    stored(project, {"app.py": Checked([])})
    store_file(project).write_bytes(corruption)
    assert reused(project, ["app.py"]) == {}


def test_a_truncated_store_is_a_miss(project: Path) -> None:
    stored(project, {"app.py": Checked([FINDING])})
    data = store_file(project).read_bytes()
    store_file(project).write_bytes(data[:-5])
    assert reused(project, ["app.py"]) == {}


def test_a_store_sealed_with_another_key_is_a_miss(project: Path) -> None:
    stored(project, {"app.py": Checked([])}, secret=bytes(32))
    assert reused(project, ["app.py"]) == {}


def resealed(cache: OutcomeCache, document: object) -> bytes:
    payload = json.dumps(document).encode()
    return cache.seal(payload) + SEAL_SEPARATOR + payload


def test_a_sealed_entry_for_other_inputs_is_a_miss(project: Path) -> None:
    cache = stored(project, {"app.py": Checked([])})
    store_file(project).write_bytes(resealed(cache, {"app.py": {"key": "0" * 64, "kind": "checked", "findings": []}}))
    assert reused(project, ["app.py"]) == {}


@pytest.mark.parametrize(
    "entry",
    [
        {"kind": "unchecked", "reason": "crashed"},
        {"kind": "checked", "findings": [{**finding_record(FINDING), "path": "other.py"}]},
        {"kind": "checked", "findings": "none"},
        {"kind": "mystery"},
    ],
    ids=["unchecked", "foreign-finding", "malformed-findings", "unknown-kind"],
)
def test_sealed_entries_are_still_validated(project: Path, entry: dict[str, object]) -> None:
    cache = stored(project, {"app.py": Checked([])})
    key = FileInputs(str(project)).key("app.py")
    store_file(project).write_bytes(resealed(cache, {"app.py": {"key": key, **entry}}))
    assert reused(project, ["app.py"]) == {}


@pytest.mark.parametrize("document", [[], "text", {"app.py": "entry"}], ids=["list", "string", "entry-text"])
def test_a_sealed_store_of_another_shape_is_a_miss(project: Path, document: object) -> None:
    cache = stored(project, {"app.py": Checked([])})
    store_file(project).write_bytes(resealed(cache, document))
    assert reused(project, ["app.py"]) == {}


def test_a_symlinked_store_is_not_followed(project: Path) -> None:
    stored(project, {"app.py": Checked([])})
    elsewhere = project / "elsewhere"
    store_file(project).rename(elsewhere)
    store_file(project).symlink_to(elsewhere)
    assert reused(project, ["app.py"]) == {}


def test_concurrent_runs_leave_one_complete_store(project: Path) -> None:
    first, second = opened(project), opened(project)
    first.lookup(["app.py"])
    second.lookup(["app.py"])
    list(first.recorded(iter([("app.py", Checked([FINDING]))])))
    list(second.recorded(iter([("app.py", Checked([FINDING]))])))
    assert reused(project, ["app.py"]) == {"app.py": Checked([FINDING])}
    assert [name for name in os.listdir(project / "cache") if name.endswith(".tmp")] == []


def test_an_unchanged_store_is_not_rewritten(project: Path) -> None:
    stored(project, {"app.py": Checked([])})
    before = store_file(project).stat().st_ino
    stored(project, {"app.py": Checked([])})
    assert store_file(project).stat().st_ino == before
