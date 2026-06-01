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
                 → Outbox table → Redpanda → consumers (notify / analytics / reconcile)
                 → Redis (fast reads)
Airflow → nightly analytics + reconciliation
```



## Tech stack



Python 3 · FastAPI · PostgreSQL · SQLAlchemy + Alembic · Redpanda (Kafka-compatible) · Redis · Airflow ·
Docker · Kubernetes · GCP · pytest (TDD)



## Run locally



```bash
docker compose up -d            # 1. start infrastructure (Postgres + Redpanda + Redis)
uv sync                         # 2. install dependencies
uv run alembic upgrade head     # 3. apply database migrations
uv run uvicorn app.main:app --reload   # 4. run the API
uv run pytest                   # 5. run the tests
```



API docs: http://localhost:8000/docs

### Event-driven workers

After the API is up, run the two workers (each in its own terminal):

```bash
uv run python -m app.events.run_publisher           # drains the outbox table -> Redpanda
uv run python -m app.events.run_consumer            # events -> notifications
uv run python -m app.events.run_analytics_consumer  # events -> analytics rollups
```

Reconciliation is a job (scheduled by Airflow in phase 8), runnable on demand —
it recomputes every wallet from the ledger and exits non-zero on any drift:

```bash
uv run python -m app.jobs.run_reconciliation
```

### Orchestration (Airflow)

Reconciliation and the analytics snapshot are scheduled as Airflow DAGs in `dags/`.
Airflow is **opt-in** and runs isolated — it pins older dependencies that conflict
with the app's SQLAlchemy 2.0, so it can't share the app image:

```bash
docker compose --profile airflow up -d   # Airflow UI -> http://localhost:8080
# the standalone admin password is printed in the airflow container logs
```

The DAGs (`wallet_reconciliation`, `wallet_analytics_snapshot`) shell out to the
job modules rather than importing app code. Running them against the live DB is
wired via Kubernetes (a `KubernetesPodOperator` on the app image) in phase 10;
the local Airflow is for authoring and validating the DAGs. Validate they parse
(a DB-free DagBag check — the throwaway container has no metadata DB, so
DB-backed CLI commands like `airflow dags list` won't work here):

```bash
docker compose --profile airflow run --rm airflow python -c "from airflow.models import DagBag; b = DagBag('/opt/airflow/dags', include_examples=False); print(b.import_errors or 'no import errors'); print(sorted(b.dags))"
```

To browse them in the UI instead, `docker compose --profile airflow up -d` (the
standalone container migrates its own metadata DB on startup) and open :8080.

### Tests

```bash
uv run pytest -m "not integration"   # fast unit/API tests (no Docker needed)
uv run pytest                        # everything, incl. the Redpanda end-to-end test (needs Docker)
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
- [x] Phase 7 — Redis balance cache (invalidate-on-write) + paginated transaction history
- [x] Phase 8 — Airflow DAGs (reconciliation + analytics snapshot, opt-in & isolated)
- [ ] Phase 9 — Test hardening + observability
- [ ] Phase 10 — Docker image, Kubernetes, GCP deploy
