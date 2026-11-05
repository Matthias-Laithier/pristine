# CR-5 DRY (Don't Repeat Yourself)

Many bugs and inconsistencies in software come from behaviors that should be shared and are duplicated: misaligned frontend components, backend discrepancies, and objects that do the same thing with no common class, interface, or owning entity.

If two or more things share behavior, extract a shared unit for that behavior. The unit may be a function, a class, an interface, or an owning entity. Sharing prevents inconsistencies, makes debugging easier, and produces clear diffs when editing code.

Do not overdo it. Extract only when behavior is genuinely shared. Code that merely looks similar is no reason to extract. Two implementations that look alike and serve different purposes are no shared abstraction. Premature DRY creates coupling and adds no clarity.

## Bad

```python
from typing import Protocol


class NotificationTransport(Protocol):
    def send(self, message: str) -> None: ...


def send_email_notification(
    email_transport: NotificationTransport,
    recipient,
    content,
):
    message = format_message(recipient, content)
    email_transport.send(message)


def send_sms_notification(
    sms_transport: NotificationTransport,
    recipient,
    content,
):
    message = format_message(recipient, content)
    sms_transport.send(message)
```

Message formatting is duplicated, so changing it requires synchronized edits.

## Good

```python
from typing import Protocol


class NotificationTransport(Protocol):
    def send(self, message: str) -> None: ...


def send_notification(
    transport: NotificationTransport,
    recipient,
    content,
):
    message = format_message(recipient, content)
    transport.send(message)


send_notification(email_transport, recipient, content)
send_notification(sms_transport, recipient, content)
```

The mechanics are genuinely shared: format the message and send it through whatever transport. If the variants carried a field that exists for only one of them, such as an email subject, the behavior would be similar without being shared, and unifying it would be premature DRY.
