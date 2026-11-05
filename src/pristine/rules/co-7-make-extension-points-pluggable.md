# CO-7 Make Extension Points Pluggable

When a component belongs to a family expected to have several independent implementations, such as providers, adapters, backends, transports, renderers, and agent harnesses, make it an extension point. Adding an implementation requires only a self-contained module and at most one declaration in a dedicated registry or composition file. Core business and orchestration logic depends on a shared contract. It never enumerates, imports, or branches on concrete implementations.

Keep configuration, dependencies, validation, behavior, and tests specific to an implementation within that implementation. A registry or composition root may know the concrete implementations, because its sole responsibility is assembling the system.

Never introduce a plugin architecture for a component with one implementation and no concrete extension requirement. A normal module is enough until the component becomes an extension point.

The practical test: adding an implementation never requires modifying core business or orchestration logic.

See [CO-3](co-3-design-for-combination-over-modification.md) for extending behavior through composition and [CO-4](co-4-clear-interfaces.md) for defining the shared contract.
