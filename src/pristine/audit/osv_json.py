from pristine.audit.models import AuditReport, DependencyFinding, SourceEvidence
from pristine.audit.schema import (
    MalformedNativeRecord,
    PackageIdentity,
    array,
    decode_output,
    fields,
    fixed_versions,
    object_record,
    text,
    texts,
)

__all__ = ["parse_osv_json"]

ADVISORY_FIELDS = (
    "schema_version",
    "id",
    "modified",
    "published",
    "withdrawn",
    "aliases",
    "related",
    "upstream",
    "summary",
    "details",
    "affected",
    "references",
    "severity",
    "database_specific",
    "credits",
)


def parse_osv_json(output: str, problems: tuple[str, ...] = ()) -> AuditReport:
    if not output and problems:
        return AuditReport((), (), problems)
    parser = _ResultParser(problems)
    try:
        parser.parse(decode_output(output))
    except (ValueError, RecursionError) as error:
        parser.problems.append(str(error) if isinstance(error, MalformedNativeRecord) else "invalid native JSON")
    if not any(source.package_count > 0 for source in parser.sources):
        parser.problems.append("native output has no package evidence")
    return AuditReport(tuple(parser.findings), tuple(parser.sources), tuple(parser.problems))


class _ResultParser:
    def __init__(self, problems: tuple[str, ...]) -> None:
        self.findings: list[DependencyFinding] = []
        self.sources: list[SourceEvidence] = []
        self.problems = list(problems)

    def parse(self, document: dict[str, object]) -> None:
        self._inspect(document, ("results", "experimental_config"), "native output")
        if "experimental_config" in document:
            try:
                self._analysis_config(document["experimental_config"])
            except MalformedNativeRecord as error:
                self.problems.append(str(error))
        for index, value in enumerate(array(document.get("results"), "native results")):
            try:
                self._source(value)
            except MalformedNativeRecord as error:
                self.problems.append(f"source {index}: {error}")

    def _analysis_config(self, value: object) -> None:
        config = object_record(value, "native analysis configuration")
        self._inspect(config, ("licenses",), "native analysis configuration")
        licenses = object_record(config.get("licenses"), "native license configuration")
        self._inspect(licenses, ("summary", "allowlist"), "native license configuration")
        if licenses.get("summary") is not False or "allowlist" not in licenses or licenses["allowlist"] is not None:
            raise MalformedNativeRecord("native output has unsupported analysis configuration")

    def _inspect(self, document: dict[str, object], allowed: tuple[str, ...], context: str) -> None:
        try:
            fields(document, allowed, context)
        except MalformedNativeRecord as error:
            self.problems.append(str(error))

    def _source(self, value: object) -> None:
        entry = object_record(value, "source result")
        self._inspect(entry, ("source", "packages"), "source result")
        origin = object_record(entry.get("source"), "source")
        self._inspect(origin, ("path", "type"), "source")
        path = text(origin.get("path"), "source path")
        source_type = text(origin.get("type"), "source type")
        packages = array(entry.get("packages"), "source packages")
        source = SourceEvidence(path, source_type, len(packages))
        self.sources.append(source)
        if source_type != "lockfile":
            self.problems.append("unsupported native source type")
        for index, package in enumerate(packages):
            try:
                self._package(source, package)
            except MalformedNativeRecord as error:
                self.problems.append(f"{path}: package {index}: {error}")

    def _package(self, source: SourceEvidence, value: object) -> None:
        entry = object_record(value, "package result")
        self._inspect(entry, ("package", "vulnerabilities", "groups", "dependency_groups"), "package result")
        metadata = object_record(entry.get("package"), "package")
        self._inspect(metadata, ("name", "version", "ecosystem", "purl"), "package")
        identity = PackageIdentity(
            text(metadata.get("name"), "package name"),
            text(metadata.get("version"), "package version"),
            text(metadata.get("ecosystem"), "package ecosystem"),
        )
        if identity.ecosystem != "PyPI":
            self.problems.append("unsupported native package ecosystem")
        groups = self._groups(entry)
        first_finding = len(self.findings)
        for index, advisory in enumerate(array(entry.get("vulnerabilities", []), "vulnerabilities")):
            try:
                self.findings.append(self._advisory(source, identity, advisory, groups))
            except MalformedNativeRecord as error:
                self.problems.append(f"{source.path}: {identity.package}: advisory {index}: {error}")
        if groups.keys() - {finding.advisory_id for finding in self.findings[first_finding:]}:
            self.problems.append("native groups refer to unreported advisories")
        if "purl" in metadata:
            text(metadata["purl"], "package purl")
        if "dependency_groups" in entry:
            texts(entry["dependency_groups"], "dependency groups")

    def _advisory(
        self, source: SourceEvidence, package: PackageIdentity, value: object, groups: dict[str, tuple[str, ...]]
    ) -> DependencyFinding:
        advisory = object_record(value, "advisory")
        identifier = text(advisory.get("id"), "advisory ID")
        self._inspect(advisory, ADVISORY_FIELDS, "advisory")
        aliases = self._aliases(advisory.get("aliases", []), "advisory aliases")
        releases: tuple[str, ...] = ()
        aliases = tuple(
            alias for alias in dict.fromkeys((*aliases, *groups.get(identifier, ()))) if alias != identifier
        )
        try:
            releases = fixed_versions(advisory, package)
        except MalformedNativeRecord as error:
            self.problems.append(f"{identifier}: {error}")
        return DependencyFinding(
            source.path,
            source.source_type,
            package.package,
            package.version,
            package.ecosystem,
            identifier,
            aliases,
            releases,
        )

    def _groups(self, entry: dict[str, object]) -> dict[str, tuple[str, ...]]:
        grouped: dict[str, tuple[str, ...]] = {}
        try:
            groups = array(entry.get("groups", []), "advisory groups")
        except MalformedNativeRecord as error:
            self.problems.append(str(error))
            return grouped
        for value in groups:
            try:
                self._group(value, grouped)
            except MalformedNativeRecord as error:
                self.problems.append(str(error))
        return grouped

    def _group(self, value: object, grouped: dict[str, tuple[str, ...]]) -> None:
        group = object_record(value, "advisory group")
        self._inspect(group, ("ids", "aliases", "max_severity"), "advisory group")
        identifiers = texts(group.get("ids"), "group IDs")
        if not identifiers:
            raise MalformedNativeRecord("advisory group has no IDs")
        aliases = (*identifiers, *self._aliases(group.get("aliases", []), "group aliases"))
        if grouped.keys() & set(identifiers):
            self.problems.append("advisory occurs in multiple native groups")
        for identifier in identifiers:
            grouped[identifier] = tuple(dict.fromkeys((*grouped.get(identifier, ()), *aliases)))
        if "max_severity" in group and not isinstance(group["max_severity"], str):
            raise MalformedNativeRecord("group severity is not text")

    def _aliases(self, value: object, context: str) -> tuple[str, ...]:
        aliases: list[str] = []
        try:
            entries = array(value, context)
        except MalformedNativeRecord as error:
            self.problems.append(str(error))
            return ()
        for entry in entries:
            try:
                aliases.append(text(entry, context))
            except MalformedNativeRecord as error:
                self.problems.append(str(error))
        return tuple(aliases)
