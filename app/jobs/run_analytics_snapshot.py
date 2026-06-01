"""Analytics snapshot job: python -m app.jobs.run_analytics_snapshot

Reads the transaction_stats rollup (maintained live by the analytics consumer)
and logs a point-in-time summary. Scheduled daily by Airflow (phase 8); handy as
a cron'd report or a hook for exporting to a warehouse later.
"""
import logging

from app.db.session import SessionLocal
from app.repositories.stats_repo import TransactionStatRepository

log = logging.getLogger(__name__)


def run() -> list:
    db = SessionLocal()
    try:
        stats = TransactionStatRepository(db).all()
        if not stats:
            log.info("analytics snapshot: no transactions recorded yet")
            return stats
        for s in stats:
            log.info(
                "analytics snapshot: %s %s -> count=%d total=%d minor units",
                s.currency, s.type, s.count, s.total_amount,
            )
        return stats
    finally:
        db.close()


if __name__ == "__main__":  # pragma: no cover
    logging.basicConfig(level=logging.INFO)
    run()
