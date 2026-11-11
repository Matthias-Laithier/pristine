import pytest

from tests.conftest import RunPristine, rule_findings

CHECK_ID = "TEST-3"


@pytest.mark.parametrize(
    "body",
    [
        "try { fail(); } catch (Math) { Math.random(); }",
        "try { fail(); } catch ({Math}) { Math.random(); }",
        "for (const setTimeout of fakes) { setTimeout(done, 5); }",
        "for (const Math in fakes) Math.random();",
        "for (let setTimeout = fake; ready; advance()) { setTimeout(done, 5); }",
        "try{fail()}catch(Math){Math.random()} for(const setTimeout of fakes){setTimeout(done,5)}",
    ],
)
@pytest.mark.parametrize("outer", ["", "Math.random();\n  setTimeout(done, 5);"])
def test_catch_and_loop_shadowing_is_lexically_scoped(run_pristine: RunPristine, body: str, outer: str) -> None:
    source = f"""test("local", () => {{
  {body}
  {outer}
}});"""
    _, report = run_pristine({"tests/lexical.test.ts": source})
    assert rule_findings(report, CHECK_ID) == ([(3, "warning"), (4, "warning")] if outer else [])
