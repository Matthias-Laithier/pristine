import pytest

from tests.conftest import RunPristine, rule_findings

PYTHON_CHAIN = (
    "def route(event):\n    if event.type == 'paid':\n        settle(event)\n"
    "    elif event.type is Kind.FAILED:\n        retry(event)\n    elif event.type == 3 or event.type == -4:\n"
    "        reopen(event)\n"
)
PYTHON_TWO_BRANCHES = "def route(event):\n    if event.type == 'paid':\n        settle(event)\n    elif event.type == 'failed':\n        retry(event)\n"
PYTHON_GUARDS = (
    "def route(event):\n    if event.type == 'paid':\n        return settle(event)\n"
    "    if event.type == 'failed':\n        return retry(event)\n    if event.type == 'refunded':\n        return reopen(event)\n"
)
PYTHON_MATCH = (
    "def route(event):\n    match event.type:\n        case 'paid':\n            settle(event)\n"
    "        case Kind.FAILED | Kind.LOST:\n            retry(event)\n        case 3:\n            reopen(event)\n"
)
PYTHON_TWO_CASE_MATCH = (
    "def route(event):\n    match event.type:\n        case 'paid':\n            settle(event)\n"
    "        case 'failed':\n            retry(event)\n        case other if other.startswith('x'):\n            drop(event)\n"
    "        case _:\n            reject(event)\n"
)
ERROR = [(1, "error")]
WARNING = [(1, "warning")]


@pytest.mark.parametrize(
    ("name", "source", "expected"),
    [
        ("route.py", PYTHON_CHAIN, [(2, "error")]),
        ("route.py", PYTHON_TWO_BRANCHES, []),
        ("route.py", PYTHON_GUARDS, []),
        ("route.js", "if (k === 'a') f(); else if (k == Kind.B) g(); else if ((k === 1 || k === 2)) h();", ERROR),
        ("route.js", "if (k === 'a') f(); else if (j === 'b') g(); else if (k === `c${x}`) h();", []),
        (
            "route.ts",
            "if (typeof k === 'string') f(); else if (typeof k === 'number') g(); else if (typeof k === 'object') h();",
            [],
        ),
        (
            "route.go",
            "package m\nfunc f() { if k == \"a\" { a() } else if k == pkg.RED { b() } else if k == 'c' { c() } }",
            [(2, "error")],
        ),
        ("route.go", "package m\nfunc f() { if k == x { a() } else if k == y { b() } else if k == z { c() } }", []),
        ("route.rs", 'fn f() { if k == "a" { a() } else if k == Kind::Red { b() } else if k == 3 { c() } }', ERROR),
        ("route.rs", 'fn f() { match k { "a" => a(), "b" => b(), 3 => c(), _ => d() } }', []),
        ("route.c", "void f() { if (k == 1) a(); else if (k == 'c') b(); else if (k == RED) c(); }", ERROR),
        ("route.c", "void f() { switch (k) { case 1: a(); break; case 2: b(); break; case 3: c(); } }", []),
        ("route.cs", 'class A { void F() { if (k == 1) {} else if (k == Kind.Red) {} else if (k == "s") {} } }', ERROR),
        ("route.kt", "fun f() { if (k == 1) a() else if (k == Kind.RED) b() else if (k == 2) c() }", ERROR),
        ("route.kt", "fun f() { if (k == 1) a() else { if (k == 2) b() else if (k == 3) c() } }", []),
        (
            "route.swift",
            "func f() { if k == 1 { a() } else if k == .red { b() } else if k == Kind.blue { c() } }",
            ERROR,
        ),
        ("route.swift", 'func f() { switch k { case 1: a(); case .red: b(); case "s": c(); default: d() } }', []),
        (
            "Route.java",
            "class A { void f() { if (k == 1) a(); else if (k == RED) b(); else if (k == 3) c(); } }",
            ERROR,
        ),
    ],
)
def test_if_else_if_chains(run_pristine: RunPristine, name: str, source: str, expected: list[tuple[int, str]]) -> None:
    _, report = run_pristine({name: source})
    assert rule_findings(report, "CR-14") == expected


@pytest.mark.parametrize(
    ("name", "source", "expected"),
    [
        ("route.py", PYTHON_MATCH, [(2, "warning")]),
        ("route.py", PYTHON_TWO_CASE_MATCH, []),
        ("route.js", "switch (k) { case 'a': a(); break; case Kind.B: case 3: b(); break; case 4: c(); }", WARNING),
        ("route.js", "switch (k) { case 'a': case 'b': case 'c': return true; default: return false; }", []),
        (
            "route.go",
            'package m\nfunc f() { switch k { case "a", "b": a(); case 1: b(); case 2: c() } }',
            [(2, "warning")],
        ),
        ("route.go", "package m\nfunc f() { switch { case k > 1: a(); case k < 0: b(); case k == 0: c() } }", []),
        (
            "Route.java",
            "class A { int f() { return switch (k) { case RED -> 1; case GREEN -> 2; case BLUE -> 3; }; } }",
            WARNING,
        ),
        (
            "route.cs",
            'class A { void F() { switch (k) { case 1: F(); break; case Kind.Red: G(); break; case "a": H(); break; } } }',
            WARNING,
        ),
        (
            "route.cs",
            "class A { void F() { switch (k) { case 1 when ok: F(); break; case 2: G(); break; case 3: H(); break; } } }",
            [],
        ),
        ("route.kt", 'fun f() { when (k) { 1 -> a(); Kind.RED, Kind.B -> b(); "s" -> c(); else -> d() } }', WARNING),
        ("route.kt", "fun f() { when (k) { 1 -> a(); 2 -> b(); else -> c() } }", []),
    ],
)
def test_switch_and_match(run_pristine: RunPristine, name: str, source: str, expected: list[tuple[int, str]]) -> None:
    _, report = run_pristine({name: source})
    assert rule_findings(report, "CR-14") == expected
