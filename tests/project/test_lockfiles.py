from pathlib import Path

from tests.project.conftest import RunProject, rule_findings, track_all

CONTRACT = "dev:\n\t./run\ncheck:\n\tpytest\ncheck-all: check\nbuild:\n\tdocker build .\n"
APPLICATION = {"Makefile": CONTRACT, "Dockerfile": "FROM python\n", "go.mod": "module app\n"}


def test_deployable_application_without_committed_lockfile(run_project: RunProject, tmp_path: Path) -> None:
    run_project({**APPLICATION, "go.sum": ""})
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


def test_lockfile_status_outside_git_is_reported(run_project: RunProject) -> None:
    _, report = run_project(APPLICATION)
    assert [severity for severity, _, _ in rule_findings(report, "TL-4")] == ["warning"]
