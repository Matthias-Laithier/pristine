from tests.conftest import RunPristine, rule_findings

CHECK_ID = "SAFE-9"
SOURCE = """import logging

logger.info(f"order {order_id} shipped")
log.warning("order %s shipped" % order_id)
logging.error("order {} shipped".format(order_id))
self.logger.debug("order " + order_id)
logger.log(logging.INFO, f"order {order_id} shipped")
logger.info("order " f"{order_id}")
logger.info("order " + order_id + suffix)
logger.info("order %s shipped", order_id)
logger.info("order shipped", extra={"order_id": order_id})
logger.info("order " + "shipped" + "!")
logger.info(f"order shipped")
logger.log(logging.INFO, "order %s shipped", order_id)
print(f"order {order_id} shipped")
metrics.info(f"order {order_id} shipped")
"""


def test_interpolated_log_messages_are_warnings(run_pristine: RunPristine) -> None:
    _, report = run_pristine({"orders.py": SOURCE})
    assert rule_findings(report, CHECK_ID) == [(line, "warning") for line in range(3, 10)]
