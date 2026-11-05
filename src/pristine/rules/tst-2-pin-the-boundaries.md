# TST-2 Pin the Boundaries

A behavior test feeds the exact inputs where behavior changes. A boundary may be an ordered threshold, a category, a state transition, an empty input, a malformed structure, or a permission level. Tests that only feed values deep inside one behavior cannot detect the transition to another.

For an ordered boundary, pin both sides: the last value of the old behavior and the first value of the new one. One side catches an operator flip, the other catches the threshold drifting to a neighboring value. For categorical or structural boundaries, pin the smallest representative input on each side of the behavior change.

The rule under test:

```python
FREE_DELIVERY_MINIMUM_IN_CENTS = 5_000


def is_free_delivery(total_in_cents):
    return total_in_cents > FREE_DELIVERY_MINIMUM_IN_CENTS
```

## Bad

```python
def test_free_delivery():
    assert is_free_delivery(9900)
    assert not is_free_delivery(1999)
```

Both values sit deep inside a branch. Flip `>` to `>=`, and delivery becomes free at exactly 50 euros while the suite stays green. Move the threshold to 4999 or 5001, and the suite stays green too.

## Good

```python
def test_free_delivery_boundary():
    assert not is_free_delivery(5000)
    assert is_free_delivery(5001)
```

The edge is fenced from both sides. Flip the operator or move the threshold by a single cent, and the test breaks. Nothing else in the suite needs to care about this rule. This test owns it.
