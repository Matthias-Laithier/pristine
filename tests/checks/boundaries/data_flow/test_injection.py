from tests.conftest import RunPristine, rule_findings

CHECK_ID = "SAFE-6"
PYTHON_SQL_SOURCE = """from psycopg2.extensions import quote_ident
from sqlalchemy import text
cursor.execute(f"SELECT * FROM invoices WHERE id = {invoice_id}")
cursor.execute("SELECT * FROM invoices WHERE id = %s" % invoice_id)
cursor.execute("DELETE FROM invoices WHERE id = {}".format(invoice_id))
session.execute(text("UPDATE invoices SET paid = 1 WHERE id = " + invoice_id))
cursor.execute("SELECT * FROM invoices WHERE id = %s", (invoice_id,))
cursor.execute(f"SELECT * FROM {INVOICES_TABLE} ORDER BY {SORT_COLUMNS[sort_key]}")
cursor.execute(f"DROP DATABASE {quote_ident(database_name)}")
runner.execute(f"deploy {release}")
cursor.execute(f"SELECT * FROM invoices WHERE number = '{request.GET['number']}'")
cursor.execute(f"SELECT * FROM invoices WHERE number = '{unquote(number)}'")
for table in ("invoices", "refunds"):
    cursor.execute(f"DELETE FROM {table}")
placeholders = ", ".join(["%s"] * len(invoice_ids))
cursor.execute(f"SELECT * FROM invoices WHERE id IN ({placeholders})", invoice_ids)
cursor.execute(f"SELECT * FROM invoices WHERE id IN ({', '.join(['%s'] * len(invoice_ids))})", invoice_ids)
"""
PYTHON_ESCAPING_SOURCE = """def quote_schema(bind, schema):
    preparer = bind.dialect.identifier_preparer
    return preparer.quote_schema(schema)


def escape_identifier(name):
    return '"' + name + '"'


def drop_schema(bind, cursor, schema, placeholder_label):
    cursor.execute(f"DROP SCHEMA {quote_schema(bind, schema)}")
    cursor.execute(f"DROP SCHEMA {escape_identifier(schema)}")
    cursor.execute(f"SELECT * FROM labels WHERE name = '{placeholder_label}'")
    escaped = schema
    cursor.execute(f"DROP SCHEMA {escaped}")
    clauses = ["deleted_at IS NULL"]
    clauses.append(f"name = '{placeholder_label}'")
    cursor.execute(f"SELECT * FROM labels WHERE {' AND '.join(clauses)}")
    literal_clauses = ["deleted_at IS NULL"]
    literal_clauses.append("archived = false")
    cursor.execute(f"SELECT * FROM labels WHERE {' AND '.join(literal_clauses)}")
"""
PYTHON_EXECUTION_SOURCE = """import os
import pickle
import subprocess
import yaml
subprocess.run(f"git log {branch}", shell=True)
subprocess.run(["git", "log", branch])
subprocess.run("git status", shell=True)
os.system("rm -rf " + directory)
eval(expression)
eval("1 + 1")
pickle.loads(payload)
yaml.load(stream)
yaml.load(stream, Loader=yaml.SafeLoader)
yaml.load(stream, Loader=yaml.FullLoader)
model.eval()
"""
SCRIPT_SOURCE = """import { exec as run, execFile } from "node:child_process";
import DOMPurify from "dompurify";
const themeScript = `document.documentElement.dataset.theme = "dark"`;
const { execSync } = require("child_process");
run(`git log ${branch}`);
execSync("git status");
execSync(`git log ${BRANCH}`);
execFile("git", ["log", branch]);
pattern.exec(`${text}`);
element.innerHTML = comment.body;
element.innerHTML = "";
element.innerHTML = DOMPurify.sanitize(comment.body);
const view = <div dangerouslySetInnerHTML={{ __html: comment.body }} />;
const safe = <div dangerouslySetInnerHTML={{ __html: themeScript }} />;
await prisma.$queryRawUnsafe(`SELECT * FROM invoices WHERE id = ${invoiceId}`);
await prisma.$queryRawUnsafe("SELECT * FROM invoices WHERE id = $1", invoiceId);
eval(expression);
new Function("total", body);
const placeholders = invoiceIds.map(() => "?").join(", ");
await prisma.$queryRawUnsafe(`SELECT * FROM invoices WHERE id IN (${placeholders})`, ...invoiceIds);
const sanitizedBody = comment.body;
element.innerHTML = sanitizedBody;
element.innerHTML = sanitize(comment.body);
"""


def test_python_sql_built_from_values(run_pristine: RunPristine) -> None:
    _, report = run_pristine({"invoices.py": PYTHON_SQL_SOURCE})
    assert [line for line, _ in rule_findings(report, CHECK_ID)] == [3, 4, 5, 6, 11, 12]


def test_python_trust_comes_from_escaping_apis_and_data_flow_never_from_names(run_pristine: RunPristine) -> None:
    _, report = run_pristine({"schemas.py": PYTHON_ESCAPING_SOURCE})
    assert [line for line, _ in rule_findings(report, CHECK_ID)] == [12, 13, 15, 18]


def test_python_shell_eval_and_deserialization(run_pristine: RunPristine) -> None:
    _, report = run_pristine({"jobs.py": PYTHON_EXECUTION_SOURCE})
    assert [line for line, _ in rule_findings(report, CHECK_ID)] == [5, 8, 9, 11, 12, 14]


def test_script_markup_processes_and_raw_queries(run_pristine: RunPristine) -> None:
    _, report = run_pristine({"invoices.tsx": SCRIPT_SOURCE})
    assert rule_findings(report, CHECK_ID) == [(line, "error") for line in (5, 10, 13, 15, 17, 18, 22, 23)]


def test_a_comprehension_reusing_its_loop_name_is_resolved_without_recursion(run_pristine: RunPristine) -> None:
    source = (
        "def total(calls):\n"
        "    for call in (call for call in calls):\n"
        '        cursor.execute(f"SELECT * FROM invoices WHERE id = {call}")\n'
    )
    _, report = run_pristine({"billing.py": source})
    assert report["unchecked"] == []
    assert rule_findings(report, "SAFE-6") == [(3, "error")]
