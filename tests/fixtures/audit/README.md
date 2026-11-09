# Native audit evidence

These are hand-reviewed projections of OSV-Scanner 2.7.0 JSON recorded on November 9, 2026. Source paths are replaced with stable fixture paths; package identities, advisory IDs, aliases, groups, and affected package ranges are unchanged. Unused advisory prose and metadata are omitted. Tests do not query the live database.

The vulnerable input is [OSV-Scanner's uv.lock fixture](https://github.com/google/osv-scanner/blob/v2.7.0/cmd/osv-scanner/scan/source/testdata/locks-scalibr/uv.lock): emoji 2.14.0 and protobuf 4.25.5. The clean input is [Scalibr's one-package fixture](https://github.com/google/osv-scalibr/blob/5be78a00e3c2/extractor/filesystem/language/python/uvlock/testdata/one-package.lock): emoji 2.14.0. Native exits were 1 and 0 respectively; only normal filesystem-walk, extraction-count, and end-status diagnostics were emitted.

Both scans used `scan source --format=json --all-packages --all-vulns --no-ignore --no-resolve --no-call-analysis=all --x-no-default-plugins --x-plugins=python/uvlock --verbosity=info`, an empty explicit `--config`, and one colon-prefixed absolute `--lockfile` path. Fixed releases are advisory context, not installed-version upgrade recommendations. The recordings are reference evidence, not a current security verdict.
