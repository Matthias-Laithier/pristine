from pristine.checks.boundaries.data_flow import injection, interpolated_logs, scattered_settings
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
    file_size.CHECK,
    function_size.CHECK,
    nesting.CHECK,
    comments.CHECK,
    global_placement.CHECK,
    service_location.CHECK,
    dispatch_chains.CHECK,
    greppable_names.CHECK,
    concrete_inheritance.CHECK,
    stateless_classes.CHECK,
    export_contract.CHECK,
    import_time_work.CHECK,
    scattered_settings.CHECK,
    unbounded_calls.CHECK,
    swallowed_failures.CHECK,
    task_ownership.CHECK,
    injection.CHECK,
    async_blocking.CHECK,
    unbounded_fan_out.CHECK,
    interpolated_logs.CHECK,
    global_mutation.CHECK,
    parameter_mutation.CHECK,
    model_settings_literals.CHECK,
    type_escapes.CHECK,
    naive_datetimes.CHECK,
    private_access_in_tests.CHECK,
    nondeterministic_tests.CHECK,
    dependent_oracles.CHECK,
    model_clients_in_tests.CHECK,
)
PATH_CHECKS: tuple[PathCheck, ...] = (
    asset_location.CHECK,
    directory_grouping.CHECK,
    function_clones.CHECK,
    import_cycles.CHECK,
    edited_migrations.CHECK,
    location_of_tests.CHECK,
)


def file_checks() -> list[FileCheck]:
    return list(FILE_CHECKS)


def path_checks() -> list[PathCheck]:
    return list(PATH_CHECKS)
