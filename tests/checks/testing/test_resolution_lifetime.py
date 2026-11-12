import gc
import sys
import weakref
from types import GeneratorType

import pytest

from pristine.checks.testing import script_scopes
from pristine.checks.testing.dependent_oracles.typescript import typescript_dependent_assertions
from pristine.checks.testing.nondeterministic_tests import typescript
from pristine.syntax.parsing import parse_file


def tracked_resolutions(monkeypatch: pytest.MonkeyPatch) -> list[weakref.ReferenceType[script_scopes.ScriptResolution]]:
    owners: list[weakref.ReferenceType[script_scopes.ScriptResolution]] = []
    original = script_scopes.ScriptResolution

    def tracked() -> script_scopes.ScriptResolution:
        resolution = original()
        owners.append(weakref.ref(resolution))
        return resolution

    monkeypatch.setattr(script_scopes, "ScriptResolution", tracked)
    return owners


def test_resolution_releases_tree_on_success_and_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    owners = tracked_resolutions(monkeypatch)
    for index in range(10):
        parsed = parse_file(f"{index}.test.ts", 'test("é", () => { Math.random(); });', "typescript")
        tree, alone = parsed.tree, object()
        reference = weakref.ref(parsed)
        assert len(typescript.typescript_nondeterministic_calls(parsed)) == 1
        assert len(owners) == index + 1
        del parsed
        gc.collect()
        assert reference() is None
        assert all(owner() is None for owner in owners)
        assert sys.getrefcount(tree) == sys.getrefcount(alone)

    def fail(scope: script_scopes.Node) -> dict[str, str | None]:
        raise ValueError(scope.type)

    monkeypatch.setattr(script_scopes, "scope_bindings", fail)
    parsed = parse_file("failure.test.ts", 'test("é", () => {});', "typescript")
    tree_references = sys.getrefcount(parsed.tree)
    with pytest.raises(ValueError, match="program"):
        typescript.typescript_nondeterministic_calls(parsed)
    gc.collect()
    assert all(owner() is None for owner in owners)
    assert sys.getrefcount(parsed.tree) == tree_references


def test_distinct_trees_never_share_bindings() -> None:
    sources = (
        'import { test as vérifier } from "vitest"; vérifier("é", () => { Math.random(); });',
        'const vérifier = (name: string, fn: () => void) => fn(); vérifier("é", () => { Math.random(); });',
    )
    for index in range(6):
        parsed = parse_file("same.test.ts", sources[index % 2], "typescript")
        assert len(typescript.typescript_nondeterministic_calls(parsed)) == (1 if index % 2 == 0 else 0)


def test_closed_assertion_iterator_releases_resolution_with_file(monkeypatch: pytest.MonkeyPatch) -> None:
    references = tracked_resolutions(monkeypatch)
    parsed = parse_file("x.test.ts", 'test("é", () => { expect(1).toBe(1); });', "typescript")
    iterator = typescript_dependent_assertions(parsed)
    assert isinstance(iterator, GeneratorType)
    assert next(iterator)[1].startswith("both sides")
    iterator.close()
    del iterator, parsed
    gc.collect()
    assert len(references) == 1
    assert all(reference() is None for reference in references)
