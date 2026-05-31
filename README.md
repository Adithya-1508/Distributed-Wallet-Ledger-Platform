# Wallet Ledger Platform



A distributed wallet & real-time payments backend — a mini-fintech core inspired by
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
docker compose up -d            # 1. start infrastructure (Postgres)
uv sync                         # 2. install dependencies
uv run alembic upgrade head     # 3. apply database migrations
uv run uvicorn app.main:app --reload   # 4. run the API
uv run pytest                   # 5. run the tests
```



API docs: http://localhost:8000/docs



## Roadmap



- [x] Phase 0 — Foundation (skeleton, Docker, config, migrations, TDD harness)
- [x] Phase 1 — Users & wallets
- [ ] Phase 2 — Deposit
- [ ] Phase 3 — Transfer (core)
- [ ] Phase 4 — Withdraw
- [ ] Phase 5 — Outbox + Kafka + notification consumer
- [ ] Phase 6 — Analytics & reconciliation consumers
- [ ] Phase 7 — Redis cache + transaction history
- [ ] Phase 8 — Airflow jobs
- [ ] Phase 9 — Test hardening + observability
- [ ] Phase 10 — Docker image, Kubernetes, GCP deploy