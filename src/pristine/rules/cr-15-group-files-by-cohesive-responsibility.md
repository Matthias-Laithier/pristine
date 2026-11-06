# CR-15 Group Files by Cohesive Responsibility

Keep each directory focused on one recognizable responsibility. 8 code files directly in a directory is the target, 15 is the hard limit. When a directory passes 8, or its files form several stable groups earlier, create clearly named subdirectories and move each group together. Choose boundaries that explain ownership, such as a feature, a domain, an external system, or an asset type. Update imports, references, build configuration, and tooling as part of the move.

The count covers the code files that sit directly in the directory, as [CR-1](cr-1-code-file-size.md) defines code. Subdirectories, data, and prose do not count. An empty `__init__.py`, a type declaration file (`.d.ts`), and a story file (`.stories.tsx`) do not count either. A non-empty `__init__.py` holds code and counts.

A flat directory is fine while its files remain one small, coherent set. Never create a folder to hold one file, and never replace one crowded directory with vague buckets such as `common/`, `misc/`, or `helpers/`. A directory name tells the reader what belongs there.

The exceptions are framework-mandated layouts, generated code, vendored code, and ordered migration directories. Follow their required structure. They cover:
- JavaScript, TypeScript, Vue, and Svelte files directly in a `pages/` or `routes/` directory, where a file-based router maps one file to one route.
- Go packages. A Go package is one directory, so splitting it creates new packages with their own import paths and forces unexported identifiers to become exported. The package API decides the grouping.
- Build output directories, such as `dist/` and `build/`, and folders named `generated`, since a generator writes them.
- Hidden tool directories, such as `.github/`.

Test folders mirror the source layout, as [TST-4](tst-4-tests-live-in-a-dedicated-tests-folder.md) requires, so they follow the grouping of the source and carry no limit of their own. When a constraint is not obvious from the repository, document it in the project instructions.

This rule owns general directory grouping. [CR-8](cr-8-services-live-in-a-dedicated-services-folder.md), [CR-9](cr-9-assets-live-in-an-organized-assets-folder.md), and [TST-4](tst-4-tests-live-in-a-dedicated-tests-folder.md) own the prescribed locations for those file types.

## Bad

```
backend/
    src/
        account.py
        account_policy.py
        invoice.py
        invoice_calculation.py
        invoice_formatting.py
        invoice_validation.py
        notification.py
        notification_preferences.py
        notification_rendering.py
```

Nine code files pass the target of 8, and they mix three recognizable domains in one flat list. Each new file makes ownership harder to see.

## Good

```
backend/
    src/
        accounts/
            account.py
            account_policy.py
        invoices/
            invoice.py
            invoice_calculation.py
            invoice_formatting.py
            invoice_validation.py
        notifications/
            notification.py
            notification_preferences.py
            notification_rendering.py
```

Each directory names one responsibility. A reader finds a domain from the directory listing and then inspects only the files it owns.
