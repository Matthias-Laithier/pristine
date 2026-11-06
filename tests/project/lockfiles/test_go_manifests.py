from pathlib import Path

import pytest

from tests.project.conftest import RunProject, rule_findings, track_all

from .fixtures import APPLICATION

MISSING_GO_SUM = (
    "warning",
    "deployable application (container build file Dockerfile) has no committed lockfile for go.mod; commit one of go.sum",
    1,
)


@pytest.mark.parametrize(
    ("go_mod", "expected"),
    [
        ("module app\n\ngo 1.24\n", []),
        ("module app\n\ngo 1.24\n\nrequire example.com/external v1.0.0\n", [MISSING_GO_SUM]),
        (
            "module app\n\ngo 1.24\n\nrequire example.com/external v1.0.0\n\nreplace example.com/external => ../local\n",
            [],
        ),
        (
            "module app\n\ngo 1.24\n\nrequire (\n\texample.com/external v1.0.0\n)\n\nreplace (\n\texample.com/external => ../local\n)\n",
            [],
        ),
        (
            "module app\n\ngo 1.24\n\nrequire example.com/external v1.0.0\n\nreplace example.com/external v1.1.0 => ../local\n",
            [MISSING_GO_SUM],
        ),
        (
            "module app\n\ngo 1.24\n\nrequire example.com/external v1.0.0\n\nreplace example.com/external => example.com/other v1.0.0\n",
            [MISSING_GO_SUM],
        ),
        (
            "module app\n\ngo 1.24\n\nrequire example.com/external v1.0.0\n\nreplace example.com/external => unknown\n",
            [
                (
                    "warning",
                    (
                        "cannot verify that the lockfile for go.mod is needed: the replace directives are not "
                        "supported by this parser"
                    ),
                    1,
                )
            ],
        ),
    ],
)
def test_go_lockfile_need_follows_external_requirements(
    run_project: RunProject, tmp_path: Path, go_mod: str, expected: list[tuple[str, str, int]]
) -> None:
    run_project({**APPLICATION, "go.mod": go_mod})
    track_all(tmp_path)
    _, report = run_project({})
    assert rule_findings(report, "TL-4") == expected


def test_exact_replacement_overrides_wildcard_replacement(run_project: RunProject, tmp_path: Path) -> None:
    go_mod = (
        "module app\n\ngo 1.24\n\nrequire example.com/external v1.0.0\n\n"
        "replace example.com/external => ../wildcard\n"
        "replace example.com/external v1.0.0 => ../local\n"
    )
    run_project({**APPLICATION, "go.mod": go_mod})
    track_all(tmp_path)
    _, report = run_project({})
    assert rule_findings(report, "TL-4") == []


@pytest.mark.parametrize(
    "go_mod",
    [
        "module app\n\ngo 1.24\n\nrequire example.com/external v1.0.0\n\nreplace example.com/external => ../local\n",
        "module app\n\ngo 1.24\n\nrequire (\n\texample.com/external v1.0.0\n)\n\nreplace (\n\texample.com/external => ../local\n)\n",
    ],
)
def test_wildcard_local_replacements_remove_the_only_go_sum_requirement(
    run_project: RunProject, tmp_path: Path, go_mod: str
) -> None:
    run_project({**APPLICATION, "go.mod": go_mod})
    track_all(tmp_path)
    _, report = run_project({})
    assert rule_findings(report, "TL-4") == []


def test_quoted_local_replacement_with_spaces_removes_the_go_sum_requirement(
    run_project: RunProject, tmp_path: Path
) -> None:
    go_mod = 'module app\n\ngo 1.24\n\nrequire example.com/external v1.0.0\n\nreplace example.com/external => "../my local"\n'
    run_project({**APPLICATION, "go.mod": go_mod})
    track_all(tmp_path)
    _, report = run_project({})
    assert rule_findings(report, "TL-4") == []


def test_malformed_go_replacement_is_unchecked(run_project: RunProject, tmp_path: Path) -> None:
    go_mod = (
        'module app\n\ngo 1.24\n\nrequire example.com/external v1.0.0\n\nreplace example.com/external => "../local\n'
    )
    run_project({**APPLICATION, "go.mod": go_mod})
    track_all(tmp_path)
    exit_code, report = run_project({})
    assert exit_code == 3
    assert report["verification_status"] == "incomplete"
    assert report["summary"]["verification_failures"] == 1
    assert report["unchecked"] == [{"path": str(tmp_path / "go.mod"), "reason": "invalid go.mod: No closing quotation"}]
