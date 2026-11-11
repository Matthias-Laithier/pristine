import pytest

from tests.conftest import RunPristine, rule_findings

BASE = "class Ledger { settle(order) { const total = order.total; return total; } }\n"
VARIANT = "class Paid extends Ledger { settle(order) { return order.paid; } }\n"
STATIC = "export class Totals { static calculate(order) { return order.total; } }\n"
MUTATION = "export function mark(order: {paid: boolean}) {\n  order.paid = true;\n}\n"


@pytest.mark.parametrize("suffix", ["js", "ts", "tsx"])
def test_script_concrete_override_and_static_namespace(run_pristine: RunPristine, suffix: str) -> None:
    _, report = run_pristine({f"ledger.{suffix}": BASE + VARIANT + STATIC})
    assert rule_findings(report, "DEP-1") == [(2, "warning")]
    assert rule_findings(report, "DEP-2") == [(3, "warning")]


@pytest.mark.parametrize(
    "source",
    [
        BASE + VARIANT + "class Other extends Ledger {}",
        BASE + VARIANT + "class Other extends Ledger implements Extension {}",
        BASE + VARIANT + "function factory() { return class extends Ledger {}; }",
        BASE.replace("Ledger", "LedgerBase") + VARIANT.replace("Ledger", "LedgerBase"),
        BASE.replace("const total = order.total; return total;", "return 1;") + VARIANT,
        BASE.replace("class Ledger", "abstract class Ledger") + VARIANT,
        "import { Ledger } from './base';\n" + VARIANT,
        BASE.replace("class Ledger", "class Ledger extends Parent") + VARIANT,
        BASE.replace("settle(order)", "static settle(order)") + VARIANT,
    ],
)
def test_uncertain_or_extension_inheritance_is_kept(run_pristine: RunPristine, source: str) -> None:
    _, report = run_pristine({"ledger.ts": source})
    assert rule_findings(report, "DEP-1") == []


@pytest.mark.parametrize(
    "source",
    [
        STATIC + "new Totals();",
        STATIC + "Totals.cache = {};",
        STATIC.replace("return order.total;", "return new Totals();"),
        STATIC + "register(Totals);",
        STATIC + "class Detailed extends Totals {}",
        STATIC.replace("static calculate", "calculate"),
        STATIC.replace("return order.total;", "return this.total;"),
        STATIC.replace("static calculate", "static total = 0; static calculate"),
        STATIC.replace("static calculate", "static other() { return 1; } static calculate"),
        STATIC.replace("class Totals", "class Totals implements Calculator"),
        STATIC.replace("class Totals", "@decorator class Totals"),
    ],
)
def test_state_instances_and_multiple_operations_are_kept(run_pristine: RunPristine, source: str) -> None:
    _, report = run_pristine({"totals.ts": source})
    assert rule_findings(report, "DEP-2") == []


def test_static_private_helper_is_kept_in_one_operation(run_pristine: RunPristine) -> None:
    source = STATIC.replace("static calculate", "private static helper() { return 1; } static calculate")
    _, report = run_pristine({"totals.ts": source})
    assert rule_findings(report, "DEP-2") == [(1, "warning")]


@pytest.mark.parametrize(
    "source",
    [
        MUTATION,
        "const queue = (items: number[]) => {\n  items.push(1);\n};",
        "function queue(items: Array<number>) {\n  items[0] += 1;\n}",
        "function index(items: Map<string, number>) {\n  items.set('a', 1);\n}",
        "function remove(items: Record<string, number>) {\n  delete items.a;\n}",
        "function clear(items: number[] | null) {\n  items?.pop();\n}",
    ],
)
def test_typed_parameter_mutation_is_reported(run_pristine: RunPristine, source: str) -> None:
    _, report = run_pristine({"orders.ts": source})
    assert rule_findings(report, "SAFE-11") == [(2, "warning")]


@pytest.mark.parametrize(
    "source",
    [
        MUTATION.replace("{paid: boolean}", "Order"),
        MUTATION.replace("order: {paid: boolean}", "order"),
        MUTATION.replace("function mark", "function _mark"),
        MUTATION + "subscribe(mark);",
        MUTATION.replace("order.paid = true;", "order = {paid: false}; order.paid = true;"),
        MUTATION.replace("order.paid = true;", "const update = (order: {paid: boolean}) => { order.paid = true; };"),
        "function save(session: Session) { session.set('a', 1); }",
        "function queue(items: ReadonlyArray<number>) { items.push(1); }",
        "type Array<T> = Custom<T>; function queue(items: Array<number>) { items.push(1); }",
        "function queue(items: number[] | Service) { items.push(1); }",
        "class Orders { mark(order: {paid: boolean}) { order.paid = true; } }",
    ],
)
def test_unproven_owned_or_rebound_parameter_mutation_is_kept(run_pristine: RunPristine, source: str) -> None:
    _, report = run_pristine({"orders.ts": source})
    assert rule_findings(report, "SAFE-11") == []


def test_script_composition_exempts_tests(run_pristine: RunPristine) -> None:
    _, report = run_pristine({"tests/orders.ts": BASE + VARIANT + STATIC + MUTATION})
    assert all(rule_findings(report, rule) == [] for rule in ["DEP-1", "DEP-2", "SAFE-11"])


def test_builtin_array_reference_does_not_shadow_its_type(run_pristine: RunPristine) -> None:
    source = "function queue(items: Array<number>) { items.push(1); } const empty = Array.from([]);"
    _, report = run_pristine({"orders.ts": source})
    assert rule_findings(report, "SAFE-11") == [(1, "warning")]


def test_destructuring_default_does_not_rebind_referenced_parameter(run_pristine: RunPristine) -> None:
    source = "function mark(order: {paid: boolean}) { const {value = order} = options; order.paid = true; }"
    _, report = run_pristine({"orders.ts": source})
    assert rule_findings(report, "SAFE-11") == [(1, "warning")]
