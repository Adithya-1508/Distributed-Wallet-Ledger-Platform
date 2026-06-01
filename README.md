# Wallet Ledger Platform



A distributed wallet & real-time payments backend - a mini-fintech core inspired by
digital banks. Built to demonstrate production-grade backend engineering: double-entry
accounting, ACID-safe money movement, event-driven architecture, and a test-driven workflow.



> **Status:** 🚧 In active development, built phase by phase. See the [Roadmap](#roadmap).



## What it does (target)



- Create users and wallets
- Deposit, transfer, and withdraw money
- Immutable **double-entry ledger** as the source of truth
- **Event-driven** fan-out (notifications, analytics, reconciliation) via Kafka
- Instant balance reads via Redis
- Scheduled analytics & reconciliation via Airflow



## Architecture (target)



```
Client → FastAPI → PostgreSQL (source of truth)
                 → Outbox table → Kafka → consumers (notify / analytics / reconcile)
                 → Redis (fast reads)
Airflow → nightly analytics + reconciliation
```



## Tech stack



Python 3 · FastAPI · PostgreSQL · SQLAlchemy + Alembic · Kafka · Redis · Airflow ·
Docker · Kubernetes · GCP · pytest (TDD)



## Run locally



```bash
docker compose up -d            # 1. start infrastructure (Postgres + Kafka)
uv sync                         # 2. install dependencies
uv run alembic upgrade head     # 3. apply database migrations
uv run uvicorn app.main:app --reload   # 4. run the API
uv run pytest                   # 5. run the tests
```



API docs: http://localhost:8000/docs

### Event-driven workers

After the API is up, run the two workers (each in its own terminal):

```bash
uv run python -m app.events.run_publisher           # drains the outbox table -> Kafka
uv run python -m app.events.run_consumer            # events -> notifications
uv run python -m app.events.run_analytics_consumer  # events -> analytics rollups
```

Reconciliation is a job (scheduled by Airflow in phase 8), runnable on demand —
it recomputes every wallet from the ledger and exits non-zero on any drift:

```bash
uv run python -m app.jobs.run_reconciliation
```

### Tests

```bash
uv run pytest -m "not integration"   # fast unit/API tests (no Docker needed)
uv run pytest                        # everything, incl. the Kafka end-to-end test (needs Docker)
```



## Roadmap



- [x] Phase 0 — Foundation (skeleton, Docker, config, migrations, TDD harness)
- [x] Phase 1 — Users & wallets
- [x] Phase 2 — Deposit (double-entry ledger, row locking, atomic commit)
- [x] Phase 3 — Transfer (deadlock-safe lock ordering, idempotency keys, insufficient-funds guard)
- [x] Phase 4 — Withdraw (DEBIT wallet / CREDIT external funding, balance guard, idempotency)
- [x] Phase 5 — Outbox + Kafka + notification consumer
  - [x] 5a — Transactional outbox (event written in the same commit as the ledger)
  - [x] 5b — Publisher worker + Kafka + notification consumer (at-least-once, idempotent consumer)
- [x] Phase 6 — Analytics consumer (idempotent rollups) & reconciliation (ledger-vs-balance drift check)
- [ ] Phase 7 — Redis cache + transaction history
- [ ] Phase 8 — Airflow jobs
- [ ] Phase 9 — Test hardening + observability
- [ ] Phase 10 — Docker image, Kubernetes, GCP deploy
