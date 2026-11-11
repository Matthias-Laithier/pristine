from pristine.catalog.check_listing import check_order
from pristine.checks.registry import FILE_CHECKS, PATH_CHECKS


def test_each_check_list_is_strictly_sorted_by_check_id() -> None:
    for checks in (FILE_CHECKS, PATH_CHECKS):
        check_ids = [check.check_id for check in checks]
        assert len(check_ids) == len(set(check_ids))
        assert check_ids == sorted(check_ids, key=lambda check_id: check_order({"check_id": check_id}))
