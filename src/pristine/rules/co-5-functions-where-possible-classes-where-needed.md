# CO-5 Functions Where Possible, Classes Where Needed

Use classes when you need state, polymorphism, enforced invariants, resource lifecycle ownership, or a framework contract. Use functions when you need none of them. A function that takes inputs and returns outputs is simpler, easier to test, and easier to compose than a class doing the same thing. Forcing stateless logic into a class adds boilerplate and implies an identity that does not exist.

Mixing paradigms is fine. A class with state and a function without state can work side by side. The choice is practical: does this unit need state, polymorphism, enforced invariants, resource lifecycle ownership, or a framework contract? If yes, use a class. If no, use a function.

## Bad

```python
class LineTotalCalculator:
    def calculate(self, unit_price, quantity):
        return unit_price * quantity


class FullNameFormatter:
    def format(self, given_name, family_name):
        return f"{given_name} {family_name}"
```

No state, no polymorphism. The classes add `self` for nothing.

## Good

```python
def calculate_line_total(unit_price, quantity):
    return unit_price * quantity


def format_full_name(given_name, family_name):
    return f"{given_name} {family_name}"
```

Same logic, no boilerplate. Easy to test and easy to compose.
