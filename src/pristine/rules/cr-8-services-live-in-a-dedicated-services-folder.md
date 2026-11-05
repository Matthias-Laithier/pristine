# CR-8 Services Live in a Dedicated `services` Folder

Every component that talks to an external system owns a `services/` folder, such as `backend/src/services/` and `worker/src/services/`. Each service gets exactly one file, named after the service, holding the service class and its external-client operations. Client construction and service assembly happen once in the application's composition root, never inside business logic. A directory listing of `services/` is the manifest of every external system the component talks to.

Services never sit scattered at the source root, and never stack into one `services.py` blob. A scattered service hides the component's external dependencies: a reader of the source root cannot tell which files talk to the outside world. A blob file has no room to grow without breaking [CR-1](cr-1-code-file-size.md), and one import of `services.py` pulls in every client the component has.

[CO-6](co-6-wrap-external-clients-in-singleton-services.md) owns the wrapping and the lifecycle. This rule owns where the service implementation lives. [CR-15](cr-15-group-files-by-cohesive-responsibility.md) owns general directory grouping.

The exceptions:
- Frameworks that prescribe the location of services as part of their contract. In those, follow the framework.
- A component with no external clients has no `services/` folder. The folder appears with the first client.

## Bad

```
backend/
    src/
        invoice_store.py
        mailer.py
        invoice.py
        report.py
        services.py
```

`invoice_store.py` and `mailer.py` sit beside pure logic with nothing marking them as the outside world. `services.py` stacks a second failure: every client in one file, one import away from constructing all of them.

## Good

```
backend/
    src/
        invoice.py
        report.py
        services/
            invoice_store.py
            mailer.py
```

The source root holds only the component's own logic. A reader listing `services/` sees the full set of external systems, each behind its own file, each importable without dragging in the others.
