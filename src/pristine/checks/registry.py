from pristine.checks.boundaries.data_flow import injection, interpolated_logs, scattered_settings, secrets
from pristine.checks.boundaries.execution import (
    async_blocking,
    swallowed_failures,
    task_ownership,
    unbounded_calls,
    unbounded_fan_out,
)
from pristine.checks.composition import (
    concrete_inheritance,
    edited_migrations,
    export_contract,
    import_cycles,
    import_time_work,
    parameter_mutation,
    stateless_classes,
)
from pristine.checks.core.placement import asset_location, directory_grouping, global_placement, service_location
from pristine.checks.core.readability import (
    comments,
    dispatch_chains,
    file_size,
    function_clones,
    function_size,
    greppable_names,
    nesting,
)
from pristine.checks.core.values import global_mutation, model_settings_literals, naive_datetimes, type_escapes
from pristine.checks.definitions import FileCheck, PathCheck
from pristine.checks.testing import (
    dependent_oracles,
    location_of_tests,
    model_clients_in_tests,
    nondeterministic_tests,
    private_access_in_tests,
)

FILE_CHECKS: tuple[FileCheck, ...] = (
    scattered_settings.CHECK,
    injection.CHECK,
    async_blocking.CHECK,
    unbounded_fan_out.CHECK,
    interpolated_logs.CHECK,
    unbounded_calls.CHECK,
    swallowed_failures.CHECK,
    task_ownership.CHECK,
    concrete_inheritance.CHECK,
    export_contract.CHECK,
    parameter_mutation.CHECK,
    import_time_work.CHECK,
    stateless_classes.CHECK,
    file_size.CHECK,
    function_size.CHECK,
    nesting.CHECK,
    dispatch_chains.CHECK,
    model_settings_literals.CHECK,
    type_escapes.CHECK,
    naive_datetimes.CHECK,
    greppable_names.CHECK,
    comments.CHECK,
    global_placement.CHECK,
    global_mutation.CHECK,
    service_location.CHECK,
    private_access_in_tests.CHECK,
    nondeterministic_tests.CHECK,
    dependent_oracles.CHECK,
    model_clients_in_tests.CHECK,
)
PATH_CHECKS: tuple[PathCheck, ...] = (
    secrets.CHECK,
    edited_migrations.CHECK,
    import_cycles.CHECK,
    directory_grouping.CHECK,
    function_clones.CHECK,
    asset_location.CHECK,
    location_of_tests.CHECK,
)


def file_checks() -> list[FileCheck]:
    return list(FILE_CHECKS)


def path_checks() -> list[PathCheck]:
    return list(PATH_CHECKS)
