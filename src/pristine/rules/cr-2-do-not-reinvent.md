# CR-2 Do Not Reinvent

Never implement from scratch what a well-maintained, accessible library or package already does. Before writing a feature, search for an existing solution. If one exists and is maintained, use it. Not Invented Here (NIH) is no valid reason to write your own.

The only exceptions:
- The library is abandoned or unmaintained.
- It has an unpatched security vulnerability.
- Its API or behavior does not fit the requirement.
- Its operational cost or dependency weight is disproportionate to the problem.
- Its license conflicts.

When you fall back to an exception, record why in the place [CR-3](cr-3-no-comments-except-machine-read-text.md) gives for a reason.

Look inside the project first. Inspect the code paths, callers, tests, and utilities related to the change, then reuse a mechanism that already fits, or extend the one that owns the responsibility. Write a new implementation only when neither works cleanly, and never force an unrelated abstraction to serve the new case.

This rule owns discovery and reuse, inside the project and outside it. [CR-5](cr-5-dry-don-t-repeat-yourself.md) owns extracting behavior that is genuinely shared. [TL-4](tl-4-keep-dependencies-minimal-declared-and-audited.md) owns a dependency after adoption.

## Bad

```python
from datetime import date

year = int(invoice_date_string[0:4])
month = int(invoice_date_string[5:7])
day = int(invoice_date_string[8:10])
invoice_date = date(year, month, day)
```

The hand-written parser duplicates standard-library behavior and silently ignores malformed separators or trailing characters.

## Good

```python
from datetime import date

invoice_date = date.fromisoformat(invoice_date_string)
```

The code calls the standard library directly. The call preserves the date-only contract and owns ISO validation.
