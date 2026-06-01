"""Reconciliation job: python -m app.jobs.run_reconciliation

Recomputes every wallet's balance from the immutable ledger and compares it to
the cached wallet balance. Exits non-zero if any drift is found, so a scheduler
(Airflow, in phase 8) or CI can alert on it.
"""
import logging

from app.db.session import SessionLocal
from app.services.reconciliation_service import (
    ReconciliationReport,
    ReconciliationService,
)

log = logging.getLogger(__name__)


def run() -> ReconciliationReport:
    db = SessionLocal()
    try:
        report = ReconciliationService(db).check()
        if report.ok:
            log.info(
                "reconciliation OK: %d wallets balanced", report.wallets_checked
            )
        else:
            log.error(
                "reconciliation FAILED: %d of %d wallets drifted",
                len(report.discrepancies),
                report.wallets_checked,
            )
            for d in report.discrepancies:
                log.error(
                    "  wallet=%s cached=%d ledger=%d diff=%d",
                    d.wallet_id, d.cached_balance, d.ledger_balance, d.diff,
                )
        return report
    finally:
        db.close()


if __name__ == "__main__":  # pragma: no cover
    logging.basicConfig(level=logging.INFO)
    report = run()
    raise SystemExit(0 if report.ok else 1)
