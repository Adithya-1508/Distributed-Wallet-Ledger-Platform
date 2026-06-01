"""DAG-integrity checks: the DAGs parse, exist, and are wired sanely.

Airflow can't be installed alongside the app (its deps conflict with SQLAlchemy
2.0), so this is skipped in the normal venv and runs in an Airflow-equipped
environment -- the airflow container or a dedicated CI job. The container itself
also validates DAGs on startup (broken DAGs show as import errors in the UI /
`airflow dags list-import-errors`).
"""
import pathlib

import pytest

pytest.importorskip(
    "airflow.models",
    reason="airflow not installed (DAG validation runs in the airflow env/container)",
)

DAGS_DIR = str(pathlib.Path(__file__).resolve().parent.parent / "dags")
EXPECTED = {"wallet_reconciliation", "wallet_analytics_snapshot"}


def _dagbag():
    from airflow.models import DagBag

    return DagBag(dag_folder=DAGS_DIR, include_examples=False)


def test_dags_import_without_errors():
    bag = _dagbag()
    assert bag.import_errors == {}, bag.import_errors


def test_expected_dags_present():
    bag = _dagbag()
    assert EXPECTED.issubset(set(bag.dags))


def test_dags_have_schedule_and_tasks():
    bag = _dagbag()
    for dag_id in EXPECTED:
        dag = bag.dags[dag_id]
        assert dag.schedule_interval is not None
        assert len(dag.tasks) >= 1
