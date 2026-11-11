import pytest

from tests.conftest import RunPristine, rule_findings


@pytest.mark.parametrize("extension", ["js", "ts", "tsx"])
def test_function_settings_reads_exempt_public_and_process_values(run_pristine: RunPristine, extension: str) -> None:
    source = """const atStartup = process.env.API_URL;
function load() {
  return [process.env.API_URL, process.env['TOKEN'],
    process.env.NEXT_PUBLIC_URL, process.env.VITE_URL, process.env.PUBLIC_URL,
    process.env.PATH, process.env.NODE_ENV, process.env[dynamicKey]];
}
function main() { return process.env.API_URL; }
function shadowed(process) { return process.env.TOKEN; }
function update() { process.env.TOKEN = 'new'; delete process.env.TOKEN; }
function enabled() { return !process.env.FEATURE_FLAG; }
"""
    _, report = run_pristine({f"application.{extension}": source})
    assert rule_findings(report, "SAFE-1") == [(3, "warning"), (10, "warning")]


@pytest.mark.parametrize(
    "path", ["main.ts", "config.ts", "next.config.js", "tests/application.ts", "application.test.ts"]
)
def test_script_settings_startup_and_tests_are_exempt(run_pristine: RunPristine, path: str) -> None:
    _, report = run_pristine({path: "function load() { return process.env.API_URL; }"})
    assert rule_findings(report, "SAFE-1") == []


@pytest.mark.parametrize("extension", ["js", "ts", "tsx"])
def test_script_interpolated_logs_keep_constant_and_structured_messages(
    run_pristine: RunPristine, extension: str
) -> None:
    source = """function report(value) {
  console.log(`loaded ${value}`);
  logger.info('loaded ' + value);
  log.error(`failed ${value}`);
  console.log('loaded %s', value);
  logger.info({ value }, 'loaded');
  logger.info('loaded', { value });
  console.info(`constant`);
  metrics.log(`metric ${value}`);
  console.log(value + count);
}
"""
    _, report = run_pristine({f"application.{extension}": source})
    assert rule_findings(report, "SAFE-9") == [(2, "warning"), (3, "warning"), (4, "warning")]


@pytest.mark.parametrize("extension", ["js", "ts", "tsx"])
def test_imported_process_is_not_the_node_global(run_pristine: RunPristine, extension: str) -> None:
    _, report = run_pristine(
        {f"application.{extension}": "import process from './fake';\nfunction load() { return process.env.TOKEN; }"}
    )
    assert rule_findings(report, "SAFE-1") == []


@pytest.mark.parametrize("extension", ["js", "ts", "tsx"])
def test_process_bindings_do_not_leak_between_siblings(run_pristine: RunPristine, extension: str) -> None:
    source = """function sibling() { const process = fake; return process; }
function load() { return process.env.TOKEN; }
function destructured(input) { const {process} = input; return process.env.TOKEN; }
function renamed({process: unrelated}) { return process.env.TOKEN; }
function scopes(input) {
  for (const process of input) { consume(process.env.TOKEN); }
  try {} catch ({other: process}) { consume(process.env.TOKEN); }
  return process.env.TOKEN;
}
"""
    _, report = run_pristine({f"application.{extension}": source})
    assert rule_findings(report, "SAFE-1") == [(2, "warning"), (4, "warning"), (8, "warning")]
