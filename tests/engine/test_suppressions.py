from tests.conftest import RunPristine, rule_findings

ANY_FIXTURE = "from typing import Any\n"


def test_pragma_suppresses_every_finding_on_its_line(run_pristine: RunPristine) -> None:
    source = (
        f"{ANY_FIXTURE}"
        "def total(invoice: Any) -> Any:  # pristine: ignore\n"
        "    return invoice\n"
        "def count(invoice: Any) -> int:\n"
        "    return 1\n"
    )
    _, report = run_pristine({"billing.py": source})
    assert rule_findings(report, "SAFE-14") == [(4, "error")]


def test_inline_pragma_does_not_suppress_the_next_line(run_pristine: RunPristine) -> None:
    source = (
        f"{ANY_FIXTURE}"
        "def total(invoice: Any) -> int:  # pristine: ignore\n"
        "    return 1\n"
        "def count(invoice: Any) -> int:\n"
        "    return 1\n"
    )
    _, report = run_pristine({"billing.py": source})
    assert rule_findings(report, "SAFE-14") == [(4, "error")]


def test_standalone_pragma_suppresses_the_next_line(run_pristine: RunPristine) -> None:
    source = f"{ANY_FIXTURE}# pristine: ignore\ndef total(invoice: Any) -> int:\n    return 1\n"
    _, report = run_pristine({"billing.py": source})
    assert rule_findings(report, "SAFE-14") == []


def test_standalone_pragma_keeps_its_trailing_explanation(run_pristine: RunPristine) -> None:
    source = (
        f"{ANY_FIXTURE}"
        "# pristine: ignore because the vendor SDK types this as Any\n"
        "def total(invoice: Any) -> int:\n"
        "    return 1\n"
    )
    _, report = run_pristine({"billing.py": source})
    assert rule_findings(report, "SAFE-14") == []


def test_pragma_combines_with_a_directive_in_a_trailing_comment(run_pristine: RunPristine) -> None:
    source = f"{ANY_FIXTURE}def total(invoice: Any) -> int:  # pristine: ignore  # noqa: E501\n    return 1\n"
    _, report = run_pristine({"billing.py": source})
    assert rule_findings(report, "SAFE-14") == []
    assert rule_findings(report, "STR-4") == []


def test_pragma_combines_with_a_directive_in_a_standalone_comment(run_pristine: RunPristine) -> None:
    source = f"{ANY_FIXTURE}# noqa: E501  # pristine: ignore\ndef total(invoice: Any) -> int:\n    return 1\n"
    _, report = run_pristine({"billing.py": source})
    assert rule_findings(report, "SAFE-14") == []
    assert rule_findings(report, "STR-4") == []


def test_docstring_text_is_not_a_pragma(run_pristine: RunPristine) -> None:
    source = f'"""pristine: ignore"""\n{ANY_FIXTURE}def total(invoice: Any) -> int:\n    return 1\n'
    _, report = run_pristine({"billing.py": source})
    assert rule_findings(report, "SAFE-14") == [(3, "error")]
    assert rule_findings(report, "STR-4") == [(1, "error")]


def test_string_text_is_not_a_pragma(run_pristine: RunPristine) -> None:
    source = f'{ANY_FIXTURE}def total(invoice: Any) -> int:\n    message = "pristine: ignore"\n    return 1\n'
    _, report = run_pristine({"billing.py": source})
    assert rule_findings(report, "SAFE-14") == [(2, "error")]


def test_script_pragma_suppresses_its_line(run_pristine: RunPristine) -> None:
    source = "const invoice: any = 1; // pristine: ignore\nconst total: any = 2;\n"
    _, report = run_pristine({"billing.ts": source})
    assert rule_findings(report, "SAFE-14") == [(2, "error")]


def test_multiline_block_comment_pragma_uses_its_own_line(run_pristine: RunPristine) -> None:
    source = "type Invoice = any;\n/*\n * pristine: ignore */\ntype Total = any;\n"
    _, report = run_pristine({"billing.ts": source})
    assert rule_findings(report, "SAFE-14") == [(1, "error")]
