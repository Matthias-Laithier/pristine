# TST-3 Minimal Test Count

A test suite carries maintenance and runtime costs for as long as the behavior exists. Write the smallest suite that protects every distinct behavior and failure mode. A test earns its place only when removing it would let through a regression the remaining tests would miss. Pin behavior through the public interface (see [TST-1](tst-1-test-behavior-through-the-public-interface.md)) and at its boundaries (see [TST-2](tst-2-pin-the-boundaries.md)). Overlap is justified only when each test catches a failure the others cannot.

Minimal means sufficient. It never means the lowest number at any cost. Never merge unrelated behaviors into one test only to lower the count. The same behavior may be tested at several boundaries only when each boundary exposes a distinct failure mode.

The fast suite behind `make check` runs in seconds. Slow tests belong behind `make check-all` (see [TL-2](tl-2-make-check-is-fast-make-check-all-runs-everything.md)). A slow `make check` is a skipped suite, and a skipped suite protects nothing. Every unnecessary test adds runtime without adding protection.

Coverage is a floor and never a target. A coverage report finds behavior with no test at all. It says nothing about the quality of the tests that exist. Quotas breed shallow tests: constant checks, type checks, fragment asserts. Use coverage to find holes, never as a score.

When behavior is removed, its tests are deleted with it. Editing the assertions of a test for dead behavior until it turns green is how suites rot.

Tests are code. Every rule of [the coding rules](README.md) applies to them, [CR-1](cr-1-code-file-size.md) included.

## Bad

```python
def test_format_price_returns_a_string():
    assert isinstance(format_price_in_cents(1000), str)


def test_format_price_uses_the_eur_symbol():
    assert "EUR" in format_price_in_cents(1000)


def test_format_price_has_two_decimals():
    assert format_price_in_cents(1000).endswith(".00")


def test_format_price_handles_whole_euros():
    assert format_price_in_cents(1000) == "10.00 EUR"


def test_format_price_handles_cents():
    assert format_price_in_cents(1050) == "10.50 EUR"


def test_format_price_handles_zero():
    assert format_price_in_cents(0) == "0.00 EUR"
```

Six tests for one behavior. The first three assert fragments the exact-value cases already cover, so they add lines without adding protection.

## Good

```python
def test_format_price_renders_two_decimals_and_the_eur_symbol():
    assert format_price_in_cents(1000) == "10.00 EUR"
    assert format_price_in_cents(1050) == "10.50 EUR"
    assert format_price_in_cents(0) == "0.00 EUR"
```

One focused test pins the full contract for the same three representative values, the zero boundary included. The suite lost five tests without losing a checked behavior or combining unrelated failures.
