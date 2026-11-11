from pathlib import Path

import pytest

from pristine.services.grammars import GrammarError, language_for, parser_for


@pytest.mark.parametrize("suffix", ["py", "pyi", "ts", "tsx", "mts", "cts", "js", "jsx", "mjs", "cjs"])
def test_supported_source_suffixes(suffix: str) -> None:
    assert language_for(Path(f"source.{suffix}")) in {"python", "typescript", "tsx", "javascript"}


@pytest.mark.parametrize(
    "name",
    [
        "source.go",
        "source.rs",
        "Source.java",
        "source.kt",
        "source.rb",
        "source.php",
        "source.swift",
        "source.c",
        "Gemfile",
        "Makefile",
        "Dockerfile",
    ],
)
def test_removed_sources_never_select_a_grammar(name: str) -> None:
    assert language_for(Path(name)) is None


def test_direct_parser_request_rejects_removed_language() -> None:
    with pytest.raises(GrammarError, match="unsupported source language"):
        parser_for("go")
