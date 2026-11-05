# CR-15 Group Files by Cohesive Responsibility

Keep each directory focused on one recognizable responsibility. When its files form several stable groups, create clearly named subdirectories and move each group together. Choose boundaries that explain ownership, such as a feature, a domain, an external system, or an asset type. Update imports, references, build configuration, and tooling as part of the move.

A flat directory is fine while its files remain one small, coherent set. Never create a folder to hold one file, and never replace one crowded directory with vague buckets such as `common/`, `misc/`, or `helpers/`. A directory name tells the reader what belongs there.

The exceptions are framework-mandated layouts, generated code, vendored code, and ordered migration directories. Follow their required structure. When the constraint is not obvious from the repository, document it in the project instructions.

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

The directory mixes three recognizable domains in one flat list. Each new file makes ownership harder to see.

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
