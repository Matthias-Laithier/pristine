# TST-7 Expected Results Come From an Independent Oracle

An assertion needs a source of truth independent from the behavior it judges. Never call the code under test, one of its production helpers, or the same implementation path to calculate the expected result. Never copy the actual output into the expected value or accept generated output without review. A test that asks production code what production code should have done stays green when that code is wrong.

Expected results come from the contract. Use hand-checked values for concrete cases, explicit invariants, reviewed golden files, or a reference implementation that shares no production logic. Test helpers may construct inputs and normalize representations. They never decide the correct outcome through production behavior.

Replace the production behavior mentally with a plausible wrong result. If the assertion still passes because its expected value changes with the actual value, the oracle is not independent. This rule owns how a test determines the correct outcome. [TST-1](tst-1-test-behavior-through-the-public-interface.md) owns what the test observes.

These forms are valid:
- An invariant, property, or round-trip assertion, when the relationship itself is the contract and the two sides share no logic that could make the same defect cancel out.
- An independently written reference implementation, when it is simpler or separately sourced. Copying the production algorithm into the test is not independent.
- A generated snapshot or golden file, once review establishes it as the expected output. Regenerating it only to make the test pass verifies nothing.

## Bad

```python
def test_order_total_sums_line_totals():
    order = Order(
        lines=[
            Line(unit_price_in_cents=1200, quantity=2),
            Line(unit_price_in_cents=900, quantity=2),
        ],
    )
    expected = calculate_order_total_in_cents(order)
    assert calculate_order_total_in_cents(order) == expected
```

The same production function calculates both sides. It may return any consistently wrong value and the test stays green.

## Good

```python
def test_order_total_sums_line_totals():
    order = Order(
        lines=[
            Line(unit_price_in_cents=1200, quantity=2),
            Line(unit_price_in_cents=900, quantity=2),
        ],
    )
    assert calculate_order_total_in_cents(order) == 4200
```

The expected total is hand-checked from the contract: two lines at 1200 cents and two at 900 cents total 4200 cents. A wrong production calculation cannot change the expected value with it.
