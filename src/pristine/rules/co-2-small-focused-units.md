# CO-2 Small, Focused Units

A function, class, or module owns one cohesive responsibility and has one reason to change. A responsibility may coordinate several operations when they form one workflow. Unrelated reasons to change belong in separate units. This cohesion is the prerequisite for composability.

## Bad

```python
MONTHLY_REPORT_PATH = "report.txt"


def monthly_report(
    accounts,
    reporting_period,
    report_store,
    report_sender,
    recipient,
):
    accounts = list(accounts)
    total = sum(account.balance for account in accounts)
    lines = [f"Monthly Report - {reporting_period}"]
    lines.extend(f"{account.name}: {account.balance}" for account in accounts)
    lines.append(f"Total: {total}")
    text = "\n".join(lines)
    report_store.replace_atomically(MONTHLY_REPORT_PATH, text)
    report_sender.send(
        to=recipient,
        subject="Monthly Report",
        body=text,
        timeout=3,
    )
```

One unit holds four jobs: compute the total, build the text, write the file, send the email. The jobs are welded together. You cannot compute the total without a filesystem and an SMTP server. You cannot test any piece alone. You cannot email the report without also writing the file.

## Good

```python
MONTHLY_REPORT_PATH = "report.txt"


def total_balance(accounts):
    return sum(account.balance for account in accounts)


def format_report(accounts, reporting_period):
    lines = [f"Monthly Report - {reporting_period}"]
    lines.extend(f"{account.name}: {account.balance}" for account in accounts)
    lines.append(f"Total: {total_balance(accounts)}")
    return "\n".join(lines)


def send_report(report_sender, recipient, text):
    report_sender.send(
        to=recipient,
        subject="Monthly Report",
        body=text,
        timeout=3,
    )
```

Each unit has one job and one reason to change. The payoff is composition: the same units serve every consumer.

```python
def create_monthly_report(
    accounts,
    reporting_period,
    report_store,
    report_sender,
    recipient,
):
    accounts = list(accounts)
    text = format_report(accounts, reporting_period)
    report_store.replace_atomically(MONTHLY_REPORT_PATH, text)
    send_report(report_sender, recipient, text)
```

The orchestration function materializes the input once, so lists and one-shot iterators behave identically. A dashboard that needs the total calls `total_balance`. Emailing the report without storing it means leaving the store operation out of the composition. Testing the formatting needs no filesystem and no SMTP. Whether each unit is a function or a class is a separate concern (see [CO-5](co-5-functions-where-possible-classes-where-needed.md)). [CR-19](cr-19-keep-one-level-of-abstraction-per-function.md) owns vertical consistency inside each unit.
