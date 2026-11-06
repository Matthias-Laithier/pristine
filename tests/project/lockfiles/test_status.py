from pathlib import Path

import pytest

from tests.project.conftest import RunProject, rule_findings, track_all

from .fixtures import APPLICATION, CONTRACT


def test_deployable_application_without_committed_lockfile(run_project: RunProject, tmp_path: Path) -> None:
    run_project({**APPLICATION, "go.mod": "module app\n\ngo 1.24\n", "go.sum": ""})
    track_all(tmp_path)
    _, report = run_project({"package.json": '{"engines": {"node": "22"}}', "pnpm-lock.yaml": ""})
    assert rule_findings(report, "TL-4") == [
        (
            "warning",
            (
                "deployable application (container build file Dockerfile) has no committed lockfile for package.json; "
                "commit one of package-lock.json, npm-shrinkwrap.json, pnpm-lock.yaml, yarn.lock, bun.lock, bun.lockb"
            ),
            1,
        )
    ]


def test_lockfile_verification_needs_git_only_when_a_lockfile_is_required(
    run_project: RunProject, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    empty_path = tmp_path / "path"
    empty_path.mkdir()
    monkeypatch.setenv("PATH", str(empty_path))

    exit_code, report = run_project({**APPLICATION, "package.json": '{"engines": {"node": "22"}}'})
    assert exit_code == 3
    assert report["verification_status"] == "incomplete"
    assert report["summary"]["verification_failures"] == 1
    assert [
        finding.get("kind", "code")
        for finding in report["findings"]
        if finding["rule_id"] == "TL-4" and finding["message"].startswith("cannot verify")
    ] == ["verification"]

    (tmp_path / "package.json").unlink()
    exit_code, report = run_project(
        {
            **APPLICATION,
            "Makefile": CONTRACT.replace(
                "check:\n\tpytest\n", 'check:\n\ttest -z "$$(gofmt -l .)"\n\tgo vet ./...\n\tgo test ./...\n'
            ),
            "go.mod": "module app\n\ngo 1.24\n",
        }
    )
    assert exit_code == 0
    assert report["verification_status"] == "complete"
    assert report["summary"]["verification_failures"] == 0
    assert rule_findings(report, "TL-4") == []
