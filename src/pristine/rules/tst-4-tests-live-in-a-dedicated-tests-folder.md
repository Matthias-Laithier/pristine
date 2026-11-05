# TST-4 Tests Live in a Dedicated tests Folder

Every component of the app owns one `tests/` folder, such as `backend/tests/`, `frontend/tests/`, and `worker/tests/`. Tests never live beside source: no `test_invoice.py` next to `invoice.py`, no `__tests__` directory inside `src`, no `InvoiceList.test.jsx` beside `InvoiceList.jsx`. The source tree is the contract of the component. Tests are its first consumer and live outside it, like every other consumer.

A directory listing of `src` then shows what a component offers and hides how it is verified. Every test sits behind one door, fixtures and helpers are shared in one place, and no test code ships. Inside `tests/`, mirror the source layout. The test for `src/payments/invoice.py` lives at `tests/payments/test_invoice.py`, and the location of a test tells you what it pins.

The exceptions are ecosystems whose toolchain enforces colocation. Go's `_test.go` files sit beside the source because the go tool demands it, and Rust's `#[cfg(test)]` modules live inside the file because the language defines them that way. These rules never override the contract of an ecosystem. In those languages, follow the language.

## Bad

```
backend/
    src/
        invoice.py
        test_invoice.py
        price_formatting.py
        test_price_formatting.py
frontend/
    src/
        components/
            InvoiceList.jsx
            InvoiceList.test.jsx
```

Tests are interleaved with source files, so the source tree mixes the contract of the component with its consumer.

## Good

```
backend/
    src/
        invoice.py
        price_formatting.py
    tests/
        test_invoice.py
        test_price_formatting.py
frontend/
    src/
        components/
            InvoiceList.jsx
    tests/
        components/
            InvoiceList.test.jsx
```

The source tree reads as a manifest of what each component offers, and the mirrored tests stay discoverable behind one door.
