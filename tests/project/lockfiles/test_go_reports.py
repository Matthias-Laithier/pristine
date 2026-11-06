from pathlib import Path

from tests.project.conftest import RunProject, rule_findings, track_all

from .fixtures import APPLICATION


def test_go_replacement_and_other_manifests_are_reported_together(run_project: RunProject, tmp_path: Path) -> None:
    go_mod = (
        "module app\n\ngo 1.24\n\nrequire (\n"
        "\texample.com/external v1.0.0\n"
        "\texample.com/other v1.0.0\n"
        "\texample.com/unrelated v1.0.0\n)\n\n"
        "replace (\n\texample.com/other => ../local\n)\n"
    )
    run_project({**APPLICATION, "go.mod": go_mod, "package.json": '{"engines": {"node": "22"}}'})
    track_all(tmp_path)
    exit_code, report = run_project({})
    assert exit_code == 1
    assert rule_findings(report, "TL-4") == [
        (
            "warning",
            (
                "deployable application (container build file Dockerfile) has no committed lockfile for go.mod; "
                "commit one of go.sum"
            ),
            1,
        ),
        (
            "warning",
            (
                "deployable application (container build file Dockerfile) has no committed lockfile for package.json; "
                "commit one of package-lock.json, npm-shrinkwrap.json, pnpm-lock.yaml, yarn.lock, bun.lock, bun.lockb"
            ),
            1,
        ),
    ]


def test_go_uncertainty_and_other_manifests_are_reported_together(run_project: RunProject, tmp_path: Path) -> None:
    go_mod = (
        "module app\n\ngo 1.24\n\n"
        "require (\n\texample.com/external v1.0.0\n\texample.com/other v1.0.0\n)\n\n"
        "replace example.com/external => unknown\n"
    )
    run_project({**APPLICATION, "go.mod": go_mod, "package.json": '{"engines": {"node": "22"}}'})
    track_all(tmp_path)
    exit_code, report = run_project({})
    assert exit_code == 3
    assert report["verification_status"] == "incomplete"
    assert report["summary"]["verification_failures"] == 1
    findings = [finding for finding in report["findings"] if finding["rule_id"] == "TL-4"]
    assert [(finding.get("kind", "code"), finding["message"]) for finding in findings] == [
        (
            "verification",
            "cannot verify that the lockfile for go.mod is needed: the replace directives are not supported by this parser",
        ),
        (
            "code",
            (
                "deployable application (container build file Dockerfile) has no committed lockfile for package.json; "
                "commit one of package-lock.json, npm-shrinkwrap.json, pnpm-lock.yaml, yarn.lock, bun.lock, bun.lockb"
            ),
        ),
    ]
