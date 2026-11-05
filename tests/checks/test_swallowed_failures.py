import pytest

from tests.conftest import RunPristine, rule_findings


def python_except(caught: str, body: str, tail: str = "") -> str:
    return f"def load(path):\n    try:\n        read(path)\n    {caught}:\n        {body}\n{tail}"


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        (python_except("except", "pass"), [(4, "error")]),
        (python_except("except Exception as error", "..."), [(4, "error")]),
        (python_except("except (KeyError, BaseException)", "return []"), [(4, "warning")]),
        (python_except("except Exception", "continue"), [(4, "warning")]),
        (python_except("except Exception", "return False"), [(4, "warning")]),
        (python_except("except Exception", "return True"), []),
        (python_except("except Exception", "log(path)\n        raise"), []),
        (python_except("except ValueError", "pass"), [(4, "warning")]),
        (python_except("except ValueError", "return None"), []),
        (python_except("except (FileNotFoundError, os.error)", "pass"), [(4, "warning")]),
        (python_except("except (FileNotFoundError, DocumentNotFoundError)", "pass"), []),
        (python_except("except ValueError", "pass", "    else:\n        raise Rejected(path)\n"), []),
        (python_except("except ValueError", "logger.debug('bad %s', path)\n        return 0"), []),
        (python_except("except Exception as error", "logging.exception(error)\n        return None"), [(4, "warning")]),
        (
            python_except("except (KeyError, Exception)", "self.log.warning(path)\n        return DEFAULT_PORT"),
            [(4, "warning")],
        ),
        (python_except("except Exception", "logger.debug(path)\n        return Rejected(path)"), []),
        (python_except("except Exception", "logger.debug(path)\n        continue"), []),
    ],
)
def test_python_except_clauses(run_pristine: RunPristine, source: str, expected: list[tuple[int, str]]) -> None:
    _, report = run_pristine({"load.py": source})
    assert rule_findings(report, "BS-4") == expected


def test_python_narrow_pass_falls_back_after_a_return(run_pristine: RunPristine) -> None:
    source = (
        "def port(text):\n    try:\n        return int(text)\n    except ValueError:\n        pass\n    return 80\n"
    )
    _, report = run_pristine({"port.py": source})
    assert rule_findings(report, "BS-4") == []


@pytest.mark.parametrize(
    ("body", "expected"),
    [
        ("{}", [(1, "warning")]),
        ("{ /* best effort */ }", [(1, "warning")]),
        ("{ return null; }", [(1, "warning")]),
        ("{ return {}; }", [(1, "warning")]),
        ("{ return false; }", []),
        ("{ throw new LoadFailed(path, { cause: error }); }", []),
        ("{ console.error(error); return null; }", [(1, "warning")]),
        ("{ logger.warn(error); log.error(path); return defaultConfig; }", [(1, "warning")]),
        ("{ console.error(error); return Response.json({ error: 'failed' }, { status: 500 }); }", []),
        ("{ console.error(error); throw error; }", []),
    ],
)
def test_script_catch_blocks(run_pristine: RunPristine, body: str, expected: list[tuple[int, str]]) -> None:
    _, report = run_pristine({"load.ts": f"try {{ read(path); }} catch (error) {body}\n"})
    assert rule_findings(report, "BS-4") == expected


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
