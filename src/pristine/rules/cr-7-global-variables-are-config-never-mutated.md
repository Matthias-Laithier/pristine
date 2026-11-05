# CR-7 Global Variables Are Config, Never Mutated

Treat global variables as config. A global is initialized once and never written again. Never rebind it or mutate application state through it: no `dict` writes, no `list.append`, no counters, no current-user data. Mutation makes a global part of the program's hidden state, whose value depends on which functions ran before and in what order. Reading config must be safe from anywhere, at any time, in any order. Once a global can change application behavior based on prior calls, every reader is debugging time travel.

A value that must change while the program runs is state. State needs an owner: a class or module that owns the value and exposes methods to change it (see [CO-5](co-5-functions-where-possible-classes-where-needed.md)). Pass that owner explicitly to the code that needs it.

The exceptions are caches, plugin registries, and stable service instances.
- Caches and registries may grow only behind an encapsulated mechanism: `functools.lru_cache` for caches, a registration decorator whose module owns the registry dict. Consumers never receive direct write access.
- A service may manage internal operational state such as connection pooling, token caching, or retries. Its identity, configuration, and application state stay fixed. Consumers call the service. They never replace it, reconfigure it, or use it as a state container.

When you take an exception, the name carries the owner and the lifecycle, such as a private module-level `_rate_cache` that only its own module fills. A decision record holds anything more (see [CR-3](cr-3-no-comments-except-machine-read-text.md)).

[CO-12](co-12-localize-mutation.md) owns mutation at every scope. [CO-13](co-13-imports-do-not-perform-external-work.md) constrains the initialization of global values.

## Bad

```python
PENDING_INVOICES = []


def queue_invoice(invoice):
    PENDING_INVOICES.append(invoice)
```

The list is hidden application state. Every caller shares the same queue, so its contents depend on which functions ran before and in what order.

## Good

```python
class InvoiceQueue:
    def __init__(self):
        self.pending_invoices = []

    def add(self, invoice):
        self.pending_invoices.append(invoice)


def main():
    invoice_queue = InvoiceQueue()
    process_invoices(invoice_queue)
```

The application state has an owner created at startup and passed to its consumer. Each `InvoiceQueue` starts empty, tests instantiate a fresh one and reset no globals between runs, and two queues coexist without sharing state.

Config still belongs at the top of the file, all of it in one place. See [CR-6](cr-6-global-variables-are-defined-at-the-top-of-the-file.md).
