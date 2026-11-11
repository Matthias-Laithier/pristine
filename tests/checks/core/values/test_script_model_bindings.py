import pytest

from tests.conftest import RunPristine, rule_findings


@pytest.mark.parametrize(
    "binding",
    [
        "const client = new OpenAI();",
        "const client: OpenAI = renderer;",
    ],
)
def test_local_class_shadows_runtime_and_type_sdk_names(run_pristine: RunPristine, binding: str) -> None:
    source = f"""import OpenAI from "openai";
function render() {{
    class OpenAI {{}}
    {binding}
    client.create({{model: "invoice", temperature: 0.2}});
}}
"""
    _, report = run_pristine({"services/model.ts": source})
    assert not rule_findings(report, "SAFE-13")


@pytest.mark.parametrize(
    "source",
    [
        'let MODEL = "gpt-4o"; MODEL = settings.model; renderer.create({model: MODEL});',
        'let client = new OpenAI(); client = renderer; client.create({model: "invoice", temperature: 0.2});',
    ],
)
def test_reassigned_bindings_are_not_model_evidence(run_pristine: RunPristine, source: str) -> None:
    _, report = run_pristine({"services/model.ts": 'import OpenAI from "openai";\n' + source})
    assert not rule_findings(report, "SAFE-13")
