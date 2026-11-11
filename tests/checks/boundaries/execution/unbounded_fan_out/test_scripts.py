import pytest

from tests.conftest import RunPristine, rule_findings


@pytest.mark.parametrize("extension", ["js", "ts", "tsx"])
def test_loaded_script_collections_fan_out(run_pristine: RunPristine, extension: str) -> None:
    source = """import { loadItems } from './services/items';
async function refresh() {
  const items = await loadItems();
  return Promise.all(items.map(async item => await save(item)));
}
"""
    _, report = run_pristine({f"application.{extension}": source})
    assert rule_findings(report, "SAFE-8") == [(4, "warning")]


@pytest.mark.parametrize(
    "load",
    [
        "await localItems()",
        "[1, 2]",
        "await loadItems({ limit: 5 })",
        "await loadItems(5)",
        "await loadItems().then(extract)",
    ],
)
def test_unknown_and_bounded_loads_are_not_fan_out_defects(run_pristine: RunPristine, load: str) -> None:
    source = f"""import {{ loadItems }} from './services/items';
async function refresh() {{
  const items = {load};
  return Promise.all(items.map(async item => await save(item)));
}}
"""
    _, report = run_pristine({"application.ts": source})
    assert rule_findings(report, "SAFE-8") == []


@pytest.mark.parametrize(
    "body",
    [
        "return Promise.all(items.map(item => save(item)));",
        "return Promise.all(items.map(async item => item.name));",
        "items = [1, 2]; return Promise.all(items.map(async item => await save(item)));",
        "return Promise.all(items.slice(0, 5).map(async item => await save(item)));",
    ],
)
def test_fan_out_needs_loaded_collection_and_awaited_callback(run_pristine: RunPristine, body: str) -> None:
    source = f"""import {{ loadItems }} from './services/items';
async function refresh() {{
  let items = await loadItems();
  {body}
}}
"""
    _, report = run_pristine({"application.ts": source})
    assert rule_findings(report, "SAFE-8") == []


@pytest.mark.parametrize(
    "path,imports",
    [
        ("tests/application.ts", ""),
        ("application.ts", "import { proxyActivities } from '@temporalio/workflow';"),
    ],
)
def test_script_limiters_tests_and_workflows_are_exempt(run_pristine: RunPristine, path: str, imports: str) -> None:
    source = f"""import {{ loadItems }} from './services/items';
{imports}
async function refresh() {{
  const items = await loadItems();
  return Promise.all(items.map(async item => await save(item)));
}}
"""
    _, report = run_pristine({path: source})
    assert rule_findings(report, "SAFE-8") == []


@pytest.mark.parametrize("limited", [False, True])
def test_limiter_import_alone_does_not_bound_fan_out(run_pristine: RunPristine, *, limited: bool) -> None:
    work = "limit(() => save(item))" if limited else "save(item)"
    source = f"""import {{ loadItems }} from './services/items';
import pLimit from 'p-limit';
const limit = pLimit(4);
async function refresh() {{
  const items = await loadItems();
  return Promise.all(items.map(async item => await {work}));
}}
"""
    _, report = run_pristine({"application.ts": source})
    assert rule_findings(report, "SAFE-8") == ([] if limited else [(6, "warning")])


def test_shadowed_promises_and_parameter_collections_are_not_fan_out_defects(run_pristine: RunPristine) -> None:
    source = """import { loadItems } from './services/items';
async function refresh(Promise) {
  const items = await loadItems();
  return Promise.all(items.map(async item => await save(item)));
}
async function refreshGiven(items) {
  return Promise.all(items.map(async item => await save(item)));
}
"""
    _, report = run_pristine({"application.ts": source})
    assert rule_findings(report, "SAFE-8") == []
