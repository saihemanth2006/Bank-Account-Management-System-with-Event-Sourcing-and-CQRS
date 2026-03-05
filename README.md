# Bank Account Management System — Event Sourcing + CQRS

This project implements a bank account backend using Event Sourcing and CQRS. It provides command endpoints (write side) and query endpoints (read side) with an event store, projections, and snapshotting.

Quickstart

1. Copy environment example:

```powershell
copy .env.example .env
```

2. Build and run with Docker Compose:

```powershell
docker compose up --build
```

3. API health: `GET http://localhost:8000/health`

Key files

- `Dockerfile`, `docker-compose.yml`, `.env.example`
- `app/` contains FastAPI app, command handlers, event store, projections, and aggregate logic
- `seeds/001_init.sql` creates `events`, `snapshots`, `account_summaries`, and `transaction_history` tables

Notes

- Snapshots are created every 50 events per aggregate and stored in `snapshots` table.
- Projections are updated synchronously after events are appended.

