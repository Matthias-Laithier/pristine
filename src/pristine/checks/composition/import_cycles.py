from collections import defaultdict
from pathlib import Path, PurePath

from pristine.checks.definitions import PathCheck
from pristine.files.classification import is_generated
from pristine.imports.cycles import ImportCycle, dependency_graph, import_cycles
from pristine.imports.edges import ImportEdge, ImportReader, SourceFile
from pristine.imports.python_imports import read_python_edges
from pristine.imports.repository import with_repository_files
from pristine.imports.script_imports import read_script_edges
from pristine.reports.findings import Finding, Severity

RULE_ID = "CO-8"
CYCLE_FIXES = (
    "move the shared contract into a lower-level module that depends on neither side, invert one dependency "
    "through a contract wired at the composition root, or merge modules that cannot be separated"
)
READERS: dict[str, ImportReader] = {
    ".py": read_python_edges,
    ".ts": read_script_edges,
    ".tsx": read_script_edges,
    ".js": read_script_edges,
    ".jsx": read_script_edges,
    ".mjs": read_script_edges,
    ".cjs": read_script_edges,
    ".mts": read_script_edges,
    ".cts": read_script_edges,
}

type ImportLines = dict[str, dict[str, int]]


def read_source(path: str) -> SourceFile | None:
    try:
        text = Path(path).read_text(errors="replace")
    except OSError:
        return None
    return None if is_generated(text) else SourceFile(path, text)


def sources_by_reader(paths: list[str]) -> dict[ImportReader, list[SourceFile]]:
    sources: dict[ImportReader, list[SourceFile]] = defaultdict(list)
    for path in paths:
        reader = READERS.get(PurePath(path).suffix)
        source = None if reader is None else read_source(path)
        if reader is not None and source is not None:
            sources[reader].append(source)
    return sources


def import_lines(edges: list[ImportEdge]) -> ImportLines:
    lines: ImportLines = defaultdict(dict)
    for edge in sorted(edges, key=lambda edge: edge.line, reverse=True):
        lines[edge.source][edge.target] = edge.line
    return lines


def cycle_description(cycle: ImportCycle) -> str:
    description = " -> ".join(cycle.path)
    if cycle.component_size == len(cycle.path) - 1:
        return description
    return f"{description}, one of the cycles among {cycle.component_size} mutually dependent files"


def cycle_finding(cycle: ImportCycle, lines: ImportLines) -> Finding:
    first, following = cycle.path[0], cycle.path[1]
    message = f"import cycle {cycle_description(cycle)}; {CYCLE_FIXES}"
    return Finding(first, lines[first][following], RULE_ID, Severity.ERROR, message)


def check_import_cycles(paths: list[str]) -> list[Finding]:
    sources = sources_by_reader(with_repository_files(paths))
    edges = [edge for reader, reader_sources in sources.items() for edge in reader(reader_sources)]
    lines = import_lines(edges)
    return [cycle_finding(cycle, lines) for cycle in import_cycles(dependency_graph(edges), set(paths))]


CHECK = PathCheck(
    rule_id=RULE_ID,
    title="No Circular Dependencies",
    summary=(
        "Import cycles between files. Python imports, including lazy, dynamic with literal names, and "
        "TYPE_CHECKING ones, and relative TS and JS imports, including type-only ones, that resolve with "
        "certainty to a file of the repository. Cycles are reported when they pass through a checked file."
    ),
    run=check_import_cycles,
)
