from pristine.checks.registry import FILE_CHECKS, PATH_CHECKS


def test_each_check_list_is_strictly_sorted_by_rule_id() -> None:
    for checks in (FILE_CHECKS, PATH_CHECKS):
        rule_ids = [check.rule_id for check in checks]
        assert rule_ids == sorted(set(rule_ids))
