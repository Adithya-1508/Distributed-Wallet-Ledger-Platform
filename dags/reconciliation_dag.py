"""Daily reconciliation DAG.

Airflow runs in its OWN environment (it pins older SQLAlchemy/Flask that clash
with this app's SQLAlchemy 2.0), so this DAG does not import app code -- it shells
out to the job module, which runs in the app's environment. In Kubernetes
(phase 10) the BashOperator becomes a KubernetesPodOperator that launches the
app image; locally the command runs wherever the app venv is on PATH.
"""
from datetime import datetime

from airflow import DAG
from airflow.operators.bash import BashOperator

with DAG(
    dag_id="wallet_reconciliation",
    description="Recompute every wallet from the ledger; exits non-zero on drift.",
    schedule="@daily",
    start_date=datetime(2026, 1, 1),
    catchup=False,
    tags=["wallet", "reconciliation"],
) as dag:
    BashOperator(
        task_id="run_reconciliation",
        bash_command="python -m app.jobs.run_reconciliation",
    )
