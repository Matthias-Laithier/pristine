import pytest

from tests.conftest import RunPristine, rule_findings


@pytest.mark.parametrize(
    ("name", "source", "expected"),
    [
        ("Load.java", "class Load { void run() { try { read(); } catch (IOException e) { } } }\n", [(1, "warning")]),
        ("Load.java", "class Load { void run() { try { read(); } catch (IOException e) { log(e); } } }\n", []),
        ("Load.cs", "class Load { void Run() { try { Read(); } catch (Exception) { } } }\n", [(1, "warning")]),
        ("Load.cs", "class Load { void Run() { try { Read(); } catch (OperationCanceledException) { } } }\n", []),
        ("Load.kt", "fun run() {\n  try { read() } catch (e: IOException) { }\n}\n", [(2, "warning")]),
        ("Load.kt", "fun run() {\n  try { read() } catch (e: IOException) { log(e) }\n}\n", []),
        ("Load.kt", "fun run() {\n  try { read() } catch (e: CancellationException) { }\n}\n", []),
        ("LoadTest.java", "class LoadTest { void run() { try { read(); fail(); } catch (IOException e) { } } }\n", []),
        (
            "LoadTest.java",
            "class LoadTest { void t() { try { read(); Assert.fail(); } catch (Error e) { } } }\n",
            [(1, "warning")],
        ),
        ("LoadTest.kt", 'fun run() {\n  try { read(); fail("read") } catch (e: IOException) { }\n}\n', []),
    ],
)
def test_typed_catch_blocks(run_pristine: RunPristine, name: str, source: str, expected: list[tuple[int, str]]) -> None:
    _, report = run_pristine({name: source})
    assert rule_findings(report, "BS-4") == expected


def go_function(body: str, results: str = "error") -> str:
    return (
        f"package load\n\nfunc load(path string) {results} {{\n\tvalue, err := read(path)\n{body}\n\treturn nil\n}}\n"
    )


@pytest.mark.parametrize(
    ("body", "results", "expected"),
    [
        ("\tif err != nil {\n\t\treturn nil\n\t}", "error", [(5, "warning")]),
        ("\tif readErr != nil {\n\t\treturn nil, nil\n\t}", "(*Page, error)", [(5, "warning")]),
        ('\tif err != nil {\n\t\treturn "", 0, false, nil\n\t}', "(string, int, bool, error)", [(5, "warning")]),
        ("\tif err != nil {\n\t\treturn\n\t}", "", []),
        ("\tif err != nil {\n\t\treturn false\n\t}", "bool", []),
        ("\tif err != nil {\n\t\treturn nil, false\n\t}", "(*Page, bool)", []),
        ("\tif err != nil {\n\t\t// best effort\n\t}", "error", [(5, "warning")]),
        ("\t_ = err", "error", [(5, "warning")]),
        ("\tif closeErr != nil {\n\t\treturn\n\t}", "(page *Page, err error)", []),
        ('\tif err != nil {\n\t\tlog.Printf("read %s: %v", path, err)\n\t\treturn nil\n\t}', "error", []),
        ('\tif err != nil {\n\t\treturn fmt.Errorf("read %s: %w", path, err)\n\t}', "error", []),
        ("\tif err != nil {\n\t\tlastErr = err\n\t\treturn nil\n\t}", "error", []),
        ("\tif err != nil {\n\t\tfailures <- err\n\t\treturn nil\n\t}", "error", []),
        ("\tif errors.Is(err, io.EOF) {\n\t\treturn nil\n\t}", "error", []),
        ("\tif err == io.EOF {\n\t\treturn nil\n\t}", "error", []),
        ("\tif err != nil && !errors.As(err, &missing) {\n\t\treturn nil\n\t}", "error", []),
        ("\tif value != nil {\n\t\treturn nil\n\t}", "error", []),
        ("\t_ = value", "error", []),
        ("\tfor range paths {\n\t\tif err != nil {\n\t\t\tcontinue\n\t\t}\n\t}", "error", []),
    ],
)
def test_go_error_checks(run_pristine: RunPristine, body: str, results: str, expected: list[tuple[int, str]]) -> None:
    _, report = run_pristine({"load.go": go_function(body, results)})
    assert rule_findings(report, "BS-4") == expected
