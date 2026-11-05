# CR-1 Code File Size

150 lines is the target maximum for a code file. A file approaching this length splits along clean boundaries. A very good reason allows a file to pass 150 lines. 200 lines is the hard limit, and no code file exceeds it. A file that cannot split without creating a leaky boundary signals that the abstraction itself needs rethinking.

The rule applies to files holding logic that the application or its tooling executes: source, tests, build scripts, Makefiles, SQL, and templates with control flow. A data file that the application interprets as logic counts as code, for example a JSON workflow definition or a YAML pipeline with conditionals.

Prose and plain data are exempt: markdown docs, agent skills, JSON or YAML configs, fixtures, and translation files. Generated files and lockfiles are exempt because nobody edits them by hand.
