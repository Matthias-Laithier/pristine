# BS-8 Resources Have Explicit Owners and Lifetimes

Every resource that requires release has one explicit owner and a bounded lifetime. Files, streams, locks, transactions, temporary directories, subprocesses, threads, sockets, and external clients are closed, committed, rolled back, joined, terminated, or otherwise released on every path, failure paths included.

Use the language's structured lifetime mechanism, such as a context manager, a scoped guard, or `try` and `finally`. The code that acquires a resource owns its release unless the interface explicitly transfers ownership. Never return a live resource whose cleanup responsibility is undocumented.

The composition root may create application-lifetime resources and close them during shutdown. Shared pools and clients follow [CO-6](co-6-wrap-external-clients-in-singleton-services.md). A process ending at some point is no cleanup strategy.

## Bad

```python
def read_invoice(path):
    invoice_file = open(path, encoding="utf-8")
    return invoice_file.read()
```

The function acquires the file and never closes it. An exception during reading leaks the resource as readily as a successful return.

## Good

```python
def read_invoice(path):
    with open(path, encoding="utf-8") as invoice_file:
        return invoice_file.read()
```

The acquiring scope owns the file. It closes on successful return and on every exception path.
