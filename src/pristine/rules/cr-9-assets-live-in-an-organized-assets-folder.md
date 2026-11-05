# CR-9 Assets Live in an Organized `assets` Folder

Every component that ships static files owns an `assets/` folder at its root, beside `src/`, such as `frontend/assets/` and `worker/assets/`. Assets are files shipped read-only with the code and never rewritten at runtime: images, icons, logos, fonts, static data, templates such as email bodies, prompt templates, and eval datasets. Files the program generates while it runs, such as logs, uploads, and exports, are artifacts. Artifacts are no assets and stay out of the repository tree.

Assets never sit scattered through the source tree, beside the code that loads them, or at the repository root. A scattered asset hides from tooling and review, and code that embeds a path like `src/invoice/logo.png` welds the asset's location to one module. The folder is organized and never a dumping ground. It holds subfolders by type, such as `images/`, `fonts/`, `data/`, `prompts/`, and `evals/`, or by feature when one feature owns many assets, with one scheme per component. A flat `assets/` root of loose files is a failure mode: nothing marks which component or feature an asset serves.

The payoff is the same manifest reading as [TST-4](tst-4-tests-live-in-a-dedicated-tests-folder.md) and [CR-8](cr-8-services-live-in-a-dedicated-services-folder.md). One listing of `assets/` shows everything the component ships that is not code, and the folder is a single copy, sync, and bundle target for tooling. [CR-15](cr-15-group-files-by-cohesive-responsibility.md) owns general directory grouping.

Prompt templates and eval datasets are assets, in folders such as `assets/prompts/` and `assets/evals/`. A prompt embedded as a string in code hides among the logic. A prompt file shows every wording change as its own diff, and the eval dataset is versioned with the prompts it measures (see [TST-8](tst-8-model-quality-is-measured-by-evals-code-by-deterministic-tests.md)). [CR-18](cr-18-name-domain-significant-values.md) owns model identifiers and sampling settings, which are configuration fields.

The exceptions:
- Ecosystems that prescribe asset locations as part of their contract: Android's `res/`, iOS's `Assets.xcassets`, the `public/` folder of Rails and Next.js. In those, follow the framework.
- A component with no static files has no `assets/` folder. The folder appears with the first asset.

## Bad

```
frontend/
    src/
        components/
            InvoiceList.jsx
            acme_logo.png
            invoice_icon.png
    acme_favicon.ico
    Inter-Regular.ttf
```

The logo and icon are welded to the directory of `InvoiceList.jsx`, so no other feature can load them without a path pointing into another feature's folder. The favicon and font sit at the repository root with nothing marking them as frontend assets.

## Good

```
frontend/
    src/
        components/
            InvoiceList.jsx
    assets/
        images/
            acme_logo.png
            invoice_icon.png
            acme_favicon.ico
        fonts/
            Inter-Regular.ttf
```

One listing of `assets/` shows every file the component ships that is not code. Bundlers sync one folder. A new feature that needs the logo links it from one stable location and never reaches into another feature's source.
