import json
from pathlib import Path

import pytest

from pristine.cli.main import main
from tests.conftest import run_git


def test_growth_splits_lines_by_kind_against_the_base(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.chdir(tmp_path)
    run_git(tmp_path, "init", "-q")
    (tmp_path / "invoice.py").write_text("a = 1\nb = 2\n")
    (tmp_path / "notes.md").write_text("old\n")
    run_git(tmp_path, "add", ".")
    run_git(
        tmp_path, "-c", "user.name=t", "-c", "user.email=t@t", "-c", "commit.gpgsign=false", "commit", "-qm", "base"
    )
    (tmp_path / "invoice.py").write_text("a = 1\n")
    (tmp_path / "notes.md").unlink()
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_invoice.py").write_text("def test_a():\n    assert a == 1\n")
    (tmp_path / "uv.lock").write_text("x\ny\n")
    assert main(["growth", "HEAD", "--json"]) == 0
    document = json.loads(capsys.readouterr().out)
    assert document["lines"]["code"] == {"added": 0, "removed": 1}
    assert document["lines"]["tests"] == {"added": 2, "removed": 0}
    assert document["lines"]["other"] == {"added": 0, "removed": 1}
    assert document["lines"]["generated"] == {"added": 2, "removed": 0}
    assert (document["maintained_net"], document["files_added"], document["files_removed"]) == (0, 2, 1)


def test_growth_outside_a_repository_is_a_usage_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.chdir(tmp_path)
    assert main(["growth"]) == 2
    assert "not inside a git repository" in capsys.readouterr().err
