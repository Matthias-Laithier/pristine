import pytest

from tests.conftest import RunPristine, rule_findings

LOGGING_HEAD = "import logging\n\nLOG = logging.getLogger(__name__)\nFALLBACK = None\n"


def python_except(caught: str, body: str, tail: str = "", head: str = "") -> str:
    return f"{head}def load(path):\n    try:\n        read(path)\n    {caught}:\n        {body}\n{tail}"


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        (python_except("except", "pass"), [(4, "error")]),
        (python_except("except Exception as error", "..."), [(4, "error")]),
        (python_except("except (KeyError, BaseException)", "return []"), [(4, "warning")]),
        (python_except("except Exception", "continue"), [(4, "warning")]),
        (python_except("except Exception", "return False"), [(4, "warning")]),
        (python_except("except Exception", "return True"), []),
        (python_except("except Exception", "log(path)\n        raise"), []),
        (python_except("except ValueError", "pass"), [(4, "warning")]),
        (python_except("except ValueError", "return None"), []),
        (python_except("except ValueError", "pass").replace("read(path)", "read(path)\n        pytest.fail(path)"), []),
        (
            python_except("except", "pass").replace("read(path)", "read(path)\n        pytest.fail(path)"),
            [(5, "error")],
        ),
        (python_except("except (FileNotFoundError, os.error)", "pass"), [(4, "warning")]),
        (python_except("except (FileNotFoundError, DocumentNotFoundError)", "pass"), [(4, "warning")]),
        (python_except("except ValueError", "pass", "    else:\n        raise Rejected(path)\n"), []),
        (python_except("except ValueError", "logger.debug('bad %s', path)\n        return 0"), []),
        (python_except("except Exception", "print(path)\n        return None"), [(4, "warning")]),
        (python_except("except Exception", "logging.exception(path)\n        return None"), []),
        (python_except("except Exception", "logger.error(path)\n        return None"), []),
        (
            python_except("except Exception", "logging.exception(path)\n        return None", head=LOGGING_HEAD),
            [(8, "warning")],
        ),
        (
            python_except(
                "except (KeyError, Exception)", "LOG.warning(path)\n        return FALLBACK", head=LOGGING_HEAD
            ),
            [(8, "warning")],
        ),
        (
            python_except(
                "except Exception", "LOG.warning(path)\n        return FALLBACK", head=LOGGING_HEAD + "FALLBACK = 80\n"
            ),
            [],
        ),
        (
            python_except(
                "except Exception",
                "self.log.bind(path=path).error(path)\n        return []",
                head="import structlog\n\nself.log = structlog.get_logger()\n",
            ),
            [(7, "warning")],
        ),
        (
            python_except(
                "except Exception", "logger.error(path)\n        return 0", head="from loguru import logger\n"
            ),
            [(5, "warning")],
        ),
        (
            python_except(
                "except Exception",
                "logger.error(path)\n        return 0",
                "def report(logger):\n    logger.info(1)\n",
                head="from loguru import logger\n",
            ),
            [],
        ),
        (python_except("except Exception", "logger.debug(path)\n        return Rejected(path)"), []),
        (python_except("except Exception", "logger.debug(path)\n        continue"), []),
    ],
)
def test_python_except_clauses(run_pristine: RunPristine, source: str, expected: list[tuple[int, str]]) -> None:
    _, report = run_pristine({"load.py": source})
    assert rule_findings(report, "SAFE-4") == expected


def test_python_narrow_pass_falls_back_after_a_return(run_pristine: RunPristine) -> None:
    source = (
        "def port(text):\n    try:\n        return int(text)\n    except ValueError:\n        pass\n    return 80\n"
    )
    _, report = run_pristine({"port.py": source})
    assert rule_findings(report, "SAFE-4") == []
