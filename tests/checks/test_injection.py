from tests.conftest import RunPristine, rule_findings

RULE_ID = "BS-10"
PYTHON_SQL_SOURCE = """from sqlalchemy import text
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
cursor.execute(f"SELECT * FROM invoices WHERE id IN ({placeholders})", invoice_ids)
cursor.execute(f"SELECT * FROM invoices WHERE id IN ({', '.join(['%s'] * len(invoice_ids))})", invoice_ids)
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
"""
GO_SOURCE = """package billing
func load(ctx context.Context) {
	db.QueryContext(ctx, fmt.Sprintf("SELECT * FROM invoices WHERE id = %s", invoiceID))
	db.Exec("DELETE FROM invoices WHERE id = " + invoiceID)
	db.Query("SELECT * FROM invoices WHERE id = $1", invoiceID)
	db.Exec(fmt.Sprintf("SET search_path = %s", schema))
	exec.Command("sh", "-c", "git log "+branch)
	exec.Command("sh", "-c", "exit "+strconv.Itoa(code))
	exec.Command("git", "log", branch)
}
"""


def test_python_sql_built_from_values(run_pristine: RunPristine) -> None:
    _, report = run_pristine({"invoices.py": PYTHON_SQL_SOURCE})
    assert [line for line, _ in rule_findings(report, RULE_ID)] == [2, 3, 4, 5, 10, 11]


def test_python_shell_eval_and_deserialization(run_pristine: RunPristine) -> None:
    _, report = run_pristine({"jobs.py": PYTHON_EXECUTION_SOURCE})
    assert [line for line, _ in rule_findings(report, RULE_ID)] == [5, 8, 9, 11, 12, 14]


def test_script_markup_processes_and_raw_queries(run_pristine: RunPristine) -> None:
    _, report = run_pristine({"invoices.tsx": SCRIPT_SOURCE})
    assert rule_findings(report, RULE_ID) == [(line, "error") for line in (4, 9, 12, 14, 16, 17)]


def test_go_sql_and_shell(run_pristine: RunPristine) -> None:
    _, report = run_pristine({"billing.go": GO_SOURCE})
    assert [line for line, _ in rule_findings(report, RULE_ID)] == [3, 4, 7]
