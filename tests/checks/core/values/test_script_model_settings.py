import pytest

from tests.conftest import RunPristine, rule_findings


@pytest.mark.parametrize("suffix", ["ts", "tsx", "js"])
def test_model_settings_are_configuration_fields(run_pristine: RunPristine, suffix: str) -> None:
    source = """import OpenAI from "openai";
const MODEL = "custom-model";
const client = new OpenAI();
async function generate(settings) {
    await client.chat.completions.create({model: MODEL, temperature: 0.2, top_p: 0.8});
    await client.chat.completions.create({model: settings.model, temperature: 0, top_p: 1});
}
"""
    _, report = run_pristine({f"services/model.{suffix}": source})
    findings = rule_findings(report, "CR-18")
    assert len(findings) == 3
    assert findings == [(5, "warning")] * 3


def test_unknown_calls_only_match_model_identifiers(run_pristine: RunPristine) -> None:
    source = """async function generate(settings) {
    await renderer.create({model: "invoice", temperature: 0.2});
    await provider.create({model: "gpt-4o", temperature: 0.2});
    await provider.create({model: settings.model, temperature: settings.temperature});
}
"""
    _, report = run_pristine({"services/model.ts": source})
    assert len(rule_findings(report, "CR-18")) == 2


def test_computed_models_and_test_inputs_are_exempt(run_pristine: RunPristine) -> None:
    source = """import OpenAI from "openai";
const client = new OpenAI();
async function generate(settings) {
    await client.responses.create({model: `model-${settings.version}`, temperature: settings.temperature});
}
"""
    _, report = run_pristine({"services/model.ts": source})
    assert not rule_findings(report, "CR-18")
    _, report = run_pristine({"tests/model.test.ts": source.replace("`model-${settings.version}`", '"gpt-4o"')})
    assert not rule_findings(report, "CR-18")


def test_shorthand_model_constants_are_detected(run_pristine: RunPristine) -> None:
    source = """const model = "gpt-4o";
async function generate() {
    await provider.create({model});
}
"""
    _, report = run_pristine({"services/model.ts": source})
    assert len(rule_findings(report, "CR-18")) == 1


def test_typed_sdk_parameters_identify_custom_models(run_pristine: RunPristine) -> None:
    source = """import {OpenAI as ModelClient} from "openai";
async function generate(client: ModelClient) {
    await client.responses.create({model: "custom-model"});
}
"""
    _, report = run_pristine({"services/model.ts": source})
    assert rule_findings(report, "CR-18") == [(3, "warning")]


def test_unrelated_client_names_and_shadowed_constants_are_not_sdk_evidence(run_pristine: RunPristine) -> None:
    source = """import OpenAI from "openai";
const MODEL = "gpt-4o";
function setup() { const client = new OpenAI(); }
function render(client, MODEL) {
    client.create({model: "invoice", temperature: 0.2});
    renderer.create({model: MODEL});
}
"""
    _, report = run_pristine({"services/model.ts": source})
    assert not rule_findings(report, "CR-18")


def test_type_only_sdk_injection_is_model_evidence(run_pristine: RunPristine) -> None:
    source = """import type OpenAI from "openai";
function generate(client: OpenAI) {
    return client.responses.create({model: "custom-model", temperature: 0.2});
}
"""
    _, report = run_pristine({"services/model.ts": source})
    assert rule_findings(report, "CR-18") == [(3, "warning"), (3, "warning")]


@pytest.mark.parametrize("suffix", ["ts", "js"])
def test_sibling_constants_do_not_replace_module_bindings(run_pristine: RunPristine, suffix: str) -> None:
    source = """const MODEL = "gpt-4o";
function unrelated() { const MODEL = "invoice"; }
function generate() { provider.create({model: MODEL}); }
"""
    _, report = run_pristine({f"services/model.{suffix}": source})
    assert rule_findings(report, "CR-18") == [(3, "warning")]


def test_block_constants_resolve_only_inside_their_scope(run_pristine: RunPristine) -> None:
    source = """const MODEL = "gpt-4o";
function generate() {
    { const MODEL = "invoice"; renderer.create({model: MODEL}); }
    provider.create({model: MODEL});
    { const MODEL = "claude-sonnet"; provider.create({model: MODEL}); }
    { let MODEL; renderer.create({model: MODEL}); }
}
"""
    _, report = run_pristine({"services/model.ts": source})
    assert rule_findings(report, "CR-18") == [(4, "warning"), (5, "warning")]


def test_clients_and_constructor_aliases_resolve_in_their_own_scope(run_pristine: RunPristine) -> None:
    source = """import {OpenAI as ModelClient} from "openai";
const client = new ModelClient();
function unrelated() { const client = renderer; }
function generate() {
    client.create({model: "custom-model"});
    { const client = renderer; client.create({model: "invoice", temperature: 0.2}); }
    { const ModelClient = Renderer; const other = new ModelClient(); other.create({model: "invoice"}); }
    client.create({model: "custom-model"});
}
function render(client) { client.create({model: "invoice"}); }
"""
    _, report = run_pristine({"services/model.ts": source})
    assert rule_findings(report, "CR-18") == [(5, "warning"), (8, "warning")]


@pytest.mark.parametrize("import_line", ['import type OpenAI from "openai";', 'import {type OpenAI} from "openai";'])
def test_type_only_imports_do_not_identify_runtime_constructors(run_pristine: RunPristine, import_line: str) -> None:
    source = f"""{import_line}
const client = new OpenAI();
client.create({{model: "invoice", temperature: 0.2}});
function generate(injected: OpenAI) {{
    injected.create({{model: "custom-model"}});
    {{ const injected = renderer; injected.create({{model: "invoice"}}); }}
}}
"""
    _, report = run_pristine({"services/model.ts": source})
    assert rule_findings(report, "CR-18") == [(5, "warning")]


@pytest.mark.parametrize("parameter", ["MODEL", "{MODEL}", "[MODEL]", "...MODEL"])
@pytest.mark.parametrize("suffix", ["ts", "js"])
def test_parameter_patterns_shadow_model_constants(run_pristine: RunPristine, parameter: str, suffix: str) -> None:
    source = f"""const MODEL = "gpt-4o";
function render({parameter}) {{ renderer.create({{model: MODEL}}); }}
"""
    _, report = run_pristine({f"services/model.{suffix}": source})
    assert not rule_findings(report, "CR-18")


def test_type_names_do_not_leak_from_sibling_or_local_declarations(run_pristine: RunPristine) -> None:
    source = """import type OpenAI from "openai";
function unrelated(client: OpenAI) { client.create({model: "custom-model"}); }
function render(client) { client.create({model: "invoice"}); }
function generic<OpenAI>(client: OpenAI) { client.create({model: "invoice"}); }
function local() {
    type OpenAI = Renderer;
    const client: OpenAI = renderer;
    client.create({model: "invoice"});
}
"""
    _, report = run_pristine({"services/model.ts": source})
    assert rule_findings(report, "CR-18") == [(2, "warning")]


@pytest.mark.parametrize("suffix", ["ts", "js"])
def test_catch_loop_and_destructured_bindings_are_not_model_evidence(run_pristine: RunPristine, suffix: str) -> None:
    source = """import OpenAI from "openai";
const MODEL = "gpt-4o";
const client = new OpenAI();
function render() {
    try {} catch (MODEL) { renderer.create({model: MODEL}); }
    for (client of renderers) { client.create({model: "invoice"}); }
    { const {MODEL} = "gpt-4o"; renderer.create({model: MODEL}); }
    { const {client} = new OpenAI(); client.create({model: "invoice"}); }
}
"""
    _, report = run_pristine({f"services/model.{suffix}": source})
    assert not rule_findings(report, "CR-18")


def test_var_loop_bindings_shadow_after_the_loop(run_pristine: RunPristine) -> None:
    source = """import OpenAI from "openai";
const client = new OpenAI();
function render() {
    for (var client of renderers) {}
    client.create({model: "invoice", temperature: 0.2});
}
"""
    _, report = run_pristine({"services/model.ts": source})
    assert not rule_findings(report, "CR-18")
