# CR-2 Do Not Reinvent

Never implement from scratch what a well-maintained, accessible library or package already does. Before writing a feature, search for an existing solution. If one exists and is maintained, use it. Not Invented Here (NIH) is no valid reason to write your own.

The only exceptions:
- The library is abandoned or unmaintained.
- It has an unpatched security vulnerability.
- Its API or behavior does not fit the requirement.
- Its operational cost or dependency weight is disproportionate to the problem.
- Its license conflicts.

When you fall back to an exception, record why in an issue, an ADR, or the project documentation.

This rule owns discovery of standard-library and third-party solutions. [CR-16](cr-16-inspect-before-implementing.md) owns discovery and reuse inside the project. [TL-4](tl-4-keep-dependencies-minimal-declared-and-audited.md) owns a dependency after adoption.

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
