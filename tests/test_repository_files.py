from pathlib import Path

import pytest

from pristine.cli import main
from tests.conftest import parsed_report, run_git

SETTLE = """def settle(order):
    total = 0
    for line in order.lines:
        if line.refunded:
            continue
        total += line.amount
    order.total = total
    return total
"""


def test_checks_run_from_a_subdirectory_see_each_repository_file_once(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    run_git(tmp_path, "init", "--quiet")
    (tmp_path / "app").mkdir()
    monkeypatch.chdir(tmp_path / "app")
    Path("orders.py").write_text(f"import invoices\n\n\n{SETTLE}")
    Path("invoices.py").write_text("import orders\n")
    main(["check", ".", "--json"])
    findings = parsed_report(capsys.readouterr().out)["findings"]
    assert [
        (finding["rule_id"], finding["path"]) for finding in findings if finding["rule_id"] in {"CO-8", "CR-5"}
    ] == [("CO-8", "invoices.py")]
