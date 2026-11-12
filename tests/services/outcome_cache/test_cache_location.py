import os
from pathlib import Path

import pytest

from pristine.services.outcome_cache import cache_locations, open_outcome_cache
from pristine.services.outcome_cache.files import KEPT_OTHER_STORES, prepared_store
from tests.conftest import run_git
from tests.services.outcome_cache.conftest import Scan, write

COMMAND = ("python", "-m", "pristine.engine.worker")


def test_the_cache_lives_at_the_repository_root(tmp_path: Path) -> None:
    run_git(tmp_path, "init", "--quiet")
    (tmp_path / "src/app").mkdir(parents=True)
    root, key_directory = cache_locations([tmp_path / "src/app"], None) or (None, None)
    assert root == tmp_path / ".pristine_cache"
    assert key_directory == Path.home() / ".cache" / "pristine"


def test_outside_a_repository_the_cache_lives_in_the_scanned_directory(tmp_path: Path) -> None:
    (tmp_path / "app.py").write_text("VALUE = 1\n")
    locations = cache_locations([tmp_path / "app.py"], None)
    assert locations is not None
    assert locations[0] == tmp_path / ".pristine_cache"


def test_the_setting_overrides_both_locations(tmp_path: Path) -> None:
    assert cache_locations([Path("src")], str(tmp_path)) == (tmp_path, tmp_path)


def test_a_new_cache_ignores_itself_in_git(tmp_path: Path, scan: Scan, isolated_result_cache: Path) -> None:
    write(tmp_path, {"app.py": "VALUE = 1\n"})
    scan()
    assert (isolated_result_cache / ".gitignore").read_text() == "*\n"
    assert not (tmp_path / ".pristine_cache").exists()


def test_no_cache_inspects_every_file_and_writes_nothing(
    tmp_path: Path, scan: Scan, isolated_result_cache: Path
) -> None:
    write(tmp_path, {"app.py": "VALUE = 1\n"})
    scan()
    _, inspected = scan("--no-cache")
    assert inspected == ["app.py"]
    (isolated_result_cache / ".gitignore").unlink()
    scan("--no-cache")
    assert not (isolated_result_cache / ".gitignore").exists()


def test_an_unwritable_cache_falls_back_to_checking_every_file(
    tmp_path: Path, scan: Scan, monkeypatch: pytest.MonkeyPatch
) -> None:
    write(tmp_path, {"app.py": "VALUE = 1\n"})
    blocked = tmp_path / "blocked"
    blocked.write_text("a file where the cache directory should be\n")
    monkeypatch.setenv("PRISTINE_CACHE_DIR", str(blocked / "cache"))
    first, first_inspected = scan()
    second, second_inspected = scan()
    assert first_inspected == second_inspected == ["app.py", "blocked"]
    assert second == first


@pytest.mark.parametrize("mode", [0o644, 0o600], ids=["readable-by-others", "symlinked"])
def test_an_unsafe_key_disables_the_cache(tmp_path: Path, mode: int) -> None:
    key = tmp_path / "outcome-cache.key"
    if mode == 0o600:
        (tmp_path / "real.key").write_bytes(bytes(32))
        (tmp_path / "real.key").chmod(0o600)
        key.symlink_to(tmp_path / "real.key")
    else:
        key.write_bytes(bytes(32))
        key.chmod(mode)
    assert open_outcome_cache((tmp_path / "cache", tmp_path), COMMAND) is None


def test_another_worker_command_uses_another_store(tmp_path: Path) -> None:
    first = open_outcome_cache((tmp_path, tmp_path), COMMAND)
    second = open_outcome_cache((tmp_path, tmp_path), (*COMMAND, "--other"))
    assert first is not None
    assert second is not None
    assert first.location != second.location


def test_old_stores_are_pruned_beyond_the_most_recent(tmp_path: Path) -> None:
    names = [f"outcomes-{index}" for index in range(KEPT_OTHER_STORES + 2)]
    for age, name in enumerate(names):
        (tmp_path / name).write_text("old\n")
        os.utime(tmp_path / name, ns=(age * 10**9, age * 10**9))
    prepared_store(tmp_path, "outcomes-new")
    remaining = sorted(name for name in os.listdir(tmp_path) if name.startswith("outcomes-"))
    assert remaining == sorted(names[-KEPT_OTHER_STORES:])


def test_the_cache_directory_does_not_count_as_a_sibling_folder(
    tmp_path: Path, tmp_path_factory: pytest.TempPathFactory, scan: Scan, monkeypatch: pytest.MonkeyPatch
) -> None:
    home = tmp_path_factory.mktemp("home")
    monkeypatch.delenv("PRISTINE_CACHE_DIR")
    monkeypatch.setattr(Path, "home", lambda: home)
    write(tmp_path, {"billing/invoice.py": "TOTAL = 1\n", "main.py": "VALUE = 1\n"})
    (tmp_path / ".pristine_cache").mkdir()
    first, _ = scan()
    second, inspected = scan()
    assert (tmp_path / ".pristine_cache/.gitignore").is_file()
    assert inspected == []
    assert [finding["check_id"] for finding in first["findings"]] == ["STR-9"]
    assert second == first
