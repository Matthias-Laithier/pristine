import pytest

from tests.conftest import RunPristine, rule_findings


@pytest.mark.parametrize("extension", ["js", "ts", "tsx"])
def test_imported_sync_io_blocks_async_functions(run_pristine: RunPristine, extension: str) -> None:
    source = """import fs from 'node:fs';
import { readFileSync as read } from 'fs';
async function load() {
  fs.readFileSync('data');
  read('data');
  const later = () => fs.readFileSync('data');
  return later;
}
function synchronous() { fs.readFileSync('data'); }
async function shadowed(fs) { fs.readFileSync('data'); }
"""
    _, report = run_pristine({f"services/files.{extension}": source})
    assert rule_findings(report, "BS-13") == [(4, "error"), (5, "error")]


@pytest.mark.parametrize("extension", ["js", "ts", "tsx"])
def test_only_known_imported_operations_are_dropped(run_pristine: RunPristine, extension: str) -> None:
    source = """import axios from 'axios';
import { readFile } from 'node:fs/promises';
import fetchRemote from 'node-fetch';
async function load() {
  axios.get('https://example.com');
  readFile('data');
  fetchRemote('https://example.com');
  await readFile('data');
  const promise = axios.get('https://example.com');
  axios.get('https://example.com').catch(handle);
  void readFile('data');
  unknown.fetch();
  return promise;
}
function shadowed(axios) { axios.get('https://example.com'); }
"""
    _, report = run_pristine({f"services/files.{extension}": source})
    assert rule_findings(report, "BS-8") == [(5, "error"), (6, "error"), (7, "error")]


def test_unknown_sync_calls_and_type_imports_are_not_defects(run_pristine: RunPristine) -> None:
    source = """import type { readFile } from 'node:fs/promises';
import type fs from 'node:fs';
async function load(fs) {
  fs.readFileSync('data');
  readFile('data');
  requests.get('url');
}
"""
    _, report = run_pristine({"services/files.ts": source})
    assert rule_findings(report, "BS-8") == []
    assert rule_findings(report, "BS-13") == []


def test_async_arrow_methods_and_namespace_imports(run_pristine: RunPristine) -> None:
    source = """import * as files from 'node:fs';
import * as promises from 'node:fs/promises';
const load = async () => files.readFileSync('data');
class Store {
  async load() { files.readFileSync('data'); promises.readFile('data'); }
}
"""
    _, report = run_pristine({"services/files.ts": source})
    assert rule_findings(report, "BS-13") == [(3, "error"), (5, "error")]
    assert rule_findings(report, "BS-8") == [(5, "error")]


def test_mixed_type_imports_and_reassigned_clients_are_not_guessed(run_pristine: RunPristine) -> None:
    source = """import { type readFile, writeFile } from 'node:fs/promises';
import axios from 'axios';
axios = replacement;
function load() {
  readFile('data');
  writeFile('data', 'value');
  axios.get('url');
}
"""
    _, report = run_pristine({"services/files.ts": source})
    assert rule_findings(report, "BS-8") == [(6, "error")]


@pytest.mark.parametrize("extension", ["js", "ts", "tsx"])
def test_client_bindings_are_lexical_and_destructuring_binds_values(run_pristine: RunPristine, extension: str) -> None:
    source = """import fs from 'node:fs';
function sibling() { const fs = fake; return fs; }
async function imported() { fs.readFileSync('data'); }
async function destructured(input) { const {fs} = input; fs.readFileSync('data'); }
async function renamed({fs: unrelated}) { fs.readFileSync('data'); }
async function parameter({other: fs}) { fs.readFileSync('data'); }
async function defaults({other: fs = fallback}) { fs.readFileSync('data'); }
async function scopes(input) {
  for (const fs of input) { fs.readFileSync('data'); }
  try {} catch (fs) { fs.readFileSync('data'); }
  { const fs = fake; fs.readFileSync('data'); }
  fs.readFileSync('data');
}
"""
    _, report = run_pristine({f"services/files.{extension}": source})
    assert rule_findings(report, "BS-13") == [(3, "error"), (5, "error"), (12, "error")]


def test_function_scoped_var_masks_import_but_sibling_var_does_not(run_pristine: RunPristine) -> None:
    source = """import fs from 'node:fs';
function sibling() { var fs = fake; return fs; }
async function load() { fs.readFileSync('data'); }
async function local() { if (enabled) { var fs = fake; } fs.readFileSync('data'); }
"""
    _, report = run_pristine({"services/files.ts": source})
    assert rule_findings(report, "BS-13") == [(3, "error")]
