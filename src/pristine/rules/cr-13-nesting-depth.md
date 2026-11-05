# CR-13 Nesting Depth

2 levels of nesting is the target, 3 is the hard limit, and no code goes deeper. A level is a control-flow block inside a function: `if`, `for`, `while`, `with`, `try`, and `match` each add one level. `else` and `elif` share the level of their `if`. `match` branches are siblings and add no depth. A comprehension or a lambda counts as one level however many clauses it carries. The rule applies to executable code. Declarative files such as YAML, JSON, and Makefiles are out of scope, since their nesting is structure without control flow.

Callbacks a test framework requires to declare tests add no level: `describe`, `it`, `test`, and their setup and teardown hooks such as `beforeEach`. They are structure the framework imposes. Nesting inside them counts from zero, like a function body.

Depth is a reading debt. The reader of a statement must hold every enclosing condition in mind at once. At four levels the question "when does this run" hides behind a stack of headers that each say "maybe". Deep nesting also predicts growth: the next requirement becomes one more level on the pile.

The first remedy is the guard clause: handle the exceptional path early, then continue or return, so the main path runs flat. The second remedy is the helper: extract the deepest block into a named function and pass it what it needs. A block that cannot be named, or needs the whole surrounding context to run, is no unit (see [CO-2](co-2-small-focused-units.md)). Helpers extracted here obey [CR-12](cr-12-function-size.md).

Generated files keep the nesting their generator writes (see [CR-3](cr-3-no-comments-except-machine-read-text.md)).

## Bad

```python
MAX_OVERDUE_REMINDERS = 3
INVOICE_BATCH_SIZE = 500


def send_overdue_reminders(invoice_store, mailer, today):
    for invoice in invoice_store.stream(batch_size=INVOICE_BATCH_SIZE):
        if invoice.due_date < today:
            if not invoice.is_paid:
                if invoice.reminder_count < MAX_OVERDUE_REMINDERS:
                    mailer.send(
                        to=invoice.recipient_email,
                        subject="Overdue invoice",
                        body=format_reminder(invoice),
                    )
```

Four levels. The reader must stack four conditions to know when an email leaves, and the next rule, such as quiet hours, arrives as a fifth level.

## Good

```python
MAX_OVERDUE_REMINDERS = 3
INVOICE_BATCH_SIZE = 500


def send_overdue_reminders(invoice_store, mailer, today):
    for invoice in invoice_store.stream(batch_size=INVOICE_BATCH_SIZE):
        if invoice.is_paid:
            continue
        if invoice.due_date >= today:
            continue
        if invoice.reminder_count >= MAX_OVERDUE_REMINDERS:
            continue
        mailer.send(
            to=invoice.recipient_email,
            subject="Overdue invoice",
            body=format_reminder(invoice),
        )
```

Each guard states one rejection reason in one line, the send runs when none fired, and the body sits at 2 levels with room for one more before the limit.
