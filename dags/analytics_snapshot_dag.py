"""Daily analytics snapshot DAG.

Shells out to the snapshot job (see reconciliation_dag for why the DAG doesn't
import app code directly).
"""
from datetime import datetime

from airflow import DAG
from airflow.operators.bash import BashOperator

with DAG(
    dag_id="wallet_analytics_snapshot",
    description="Log a point-in-time summary of the transaction analytics rollup.",
    schedule="@daily",
    start_date=datetime(2026, 1, 1),
    catchup=False,
    tags=["wallet", "analytics"],
) as dag:
    BashOperator(
        task_id="run_analytics_snapshot",
        bash_command="python -m app.jobs.run_analytics_snapshot",
    )
