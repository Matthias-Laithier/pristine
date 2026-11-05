# TST-5 Every Bug Gets a Regression Test

Every fixed bug leaves behind a test that would have caught it. The sequence is fixed: reproduce the bug as a failing test, watch it fail, fix the code until the test passes, and commit both together. The test stays for as long as the behavior exists. If an automated regression test is technically impossible, leave the strongest available automated check or a documented verification, and record why in the place [CR-3](cr-3-no-comments-except-machine-read-text.md) gives for a reason.

Watching it fail is what makes the test real. A regression test that was never red has proven nothing. If the bug is technically reproducible in a test and you cannot make that test fail, you have not reproduced the bug, and the fix you are about to write is a guess.

A bug is the strongest signal a suite receives: reality proved this behavior needs a pin. The suite grows for regressions, for deliberate boundary pins, and for one minimal contract test when new behavior visible from outside lands (see [TST-2](tst-2-pin-the-boundaries.md)). A reproducible bug fixed without its test is a bug on a timer.

## Bad

```python
def total_with_coupon(cart, coupon):
    return cart.subtotal_in_cents - coupon.value_in_cents
```

A customer reports a 10 euro coupon taking 20 euros off a 100 euro cart. The fix lands: the per-item sum becomes a single `coupon.value_in_cents` subtraction. It is correct and committed, and nothing in the suite distinguishes the fixed version from the buggy one. The next refactor can reintroduce the per-item discount silently.

## Good

```python
def test_coupon_discount_applies_once_per_cart():
    cart = Cart(
        items=[
            Item(name="Keyboard", price_in_cents=8000),
            Item(name="Mouse", price_in_cents=2000),
        ],
    )
    assert total_with_coupon(cart, Coupon(value_in_cents=1000)) == 9000
```

Against the buggy per-item implementation, the test reports 8000 where 9000 is expected. Only after observing that failure, fix the production code:

```python
def total_with_coupon(cart, coupon):
    return cart.subtotal_in_cents - coupon.value_in_cents
```

The same test passes. The reported scenario stays pinned for as long as coupon behavior exists: a keyboard at 80 euros, a mouse at 20 euros, a 10 euro coupon, 90 euros due. The per-item version fails this test on every future run. The bug is dead for good.
