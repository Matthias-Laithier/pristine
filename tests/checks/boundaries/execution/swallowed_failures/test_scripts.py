import pytest

from tests.conftest import RunPristine, rule_findings


@pytest.mark.parametrize(
    ("body", "expected"),
    [
        ("{}", [(1, "warning")]),
        ("{ /* best effort */ }", [(1, "warning")]),
        ("{ return null; }", [(1, "warning")]),
        ("{ return {}; }", [(1, "warning")]),
        ("{ return false; }", []),
        ("{ throw new LoadFailed(path, { cause: error }); }", []),
        ("{ console.error(error); return null; }", [(1, "warning")]),
        ("{ logger.warn(error); return null; }", []),
        ("{ console.error(error); return Response.json({ error: 'failed' }, { status: 500 }); }", []),
        ("{ console.error(error); throw error; }", []),
    ],
)
def test_script_catch_blocks(run_pristine: RunPristine, body: str, expected: list[tuple[int, str]]) -> None:
    _, report = run_pristine({"load.ts": f"try {{ read(path); }} catch (error) {body}\n"})
    assert rule_findings(report, "SAFE-4") == expected


@pytest.mark.parametrize(
    ("head", "expected"),
    [
        ("const defaultConfig = {};\n", [(2, "warning")]),
        ("const defaultConfig = { retries: 3 };\n", []),
        ("let defaultConfig = {};\n", []),
        ("const defaultConfig = {};\nimport { console } from './terminal';\n", []),
    ],
)
def test_script_logged_defaults_resolve_console_and_constants(
    run_pristine: RunPristine, head: str, expected: list[tuple[int, str]]
) -> None:
    body = "try { read(path); } catch (error) { console.warn(error); return defaultConfig; }\n"
    _, report = run_pristine({"load.ts": head + body})
    assert rule_findings(report, "SAFE-4") == expected
