# CR-1 Code File Size

200 lines is the hard limit for a code file, and no code file exceeds it. A file approaching this length splits along clean boundaries. A file that cannot split without creating a leaky boundary signals that the abstraction itself needs rethinking.

The rule applies to files holding logic that the application or its tooling executes: source, tests, build scripts, Makefiles, SQL, and templates with control flow. A data file that the application interprets as logic counts as code, for example a JSON workflow definition or a YAML pipeline with conditionals.

Prose and plain data are exempt: markdown docs, agent skills, JSON or YAML configs, fixtures, and translation files. Generated files and lockfiles are exempt because nobody edits them by hand.
