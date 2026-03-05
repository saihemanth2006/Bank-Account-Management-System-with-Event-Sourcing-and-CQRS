from fastapi import APIRouter, HTTPException
from typing import Any, Dict
from .main import database

router = APIRouter()


async def process_event(aggregate_id: str, event: Dict[str, Any]):
    # event uses fields: event_id, event_number, event_type, event_data, timestamp
    ev_num = event.get("event_number")
    et = event.get("event_type")
    data = event.get("event_data") or {}
    ev_id = event.get("event_id")
    ev_ts = event.get("timestamp")

    # AccountCreated: create read model if not exists
    if et == "AccountCreated":
        q = """
        INSERT INTO account_summaries (account_id, owner_name, balance, currency, status, version)
        VALUES (:aid, :owner, :balance, :currency, 'OPEN', 1)
        ON CONFLICT (account_id) DO NOTHING
        """
        await database.execute(q, values={"aid": str(aggregate_id), "owner": data.get("ownerName") or data.get("owner_name"), "balance": data.get("initialBalance", 0), "currency": data.get("currency", "USD")})

    elif et in ("MoneyDeposited", "MoneyWithdrawn"):
        # idempotency via transaction_id (if provided) or event_id
        transaction_id = data.get("transactionId") or data.get("transaction_id") or str(ev_id)
        exists = await database.fetch_one("SELECT 1 FROM transaction_history WHERE transaction_id = :tid", values={"tid": transaction_id})
        if exists:
            return

        amt = data.get("amount")
        if et == "MoneyDeposited":
            uq = "UPDATE account_summaries SET balance = balance + :amt, version = version + 1 WHERE account_id = :aid"
        else:
            uq = "UPDATE account_summaries SET balance = balance - :amt, version = version + 1 WHERE account_id = :aid"
        await database.execute(uq, values={"amt": amt, "aid": str(aggregate_id)})

        tq = "INSERT INTO transaction_history (transaction_id, account_id, type, amount, description, timestamp) VALUES (:tid, :aid, :type, :amt, :desc, :ts)"
        await database.execute(tq, values={"tid": transaction_id, "aid": str(aggregate_id), "type": et, "amt": amt, "desc": data.get("description"), "ts": ev_ts})

    elif et == "AccountClosed":
        q = "UPDATE account_summaries SET status = 'CLOSED', version = version + 1 WHERE account_id = :aid"
        await database.execute(q, values={"aid": str(aggregate_id)})


@router.get("/accounts/{account_id}")
async def get_account_summary(account_id: str):
    q = "SELECT account_id, owner_name, balance, currency, status, version FROM account_summaries WHERE account_id = :aid"
    r = await database.fetch_one(q, values={"aid": str(account_id)})
    if not r:
        raise HTTPException(status_code=404, detail="Account not found")
    return {"account_id": r["account_id"], "owner_name": r["owner_name"], "balance": float(r["balance"]), "currency": r["currency"], "status": r["status"], "version": r["version"]}


@router.get("/accounts/{account_id}/transactions")
async def get_transactions(account_id: str):
    q = "SELECT transaction_id, account_id, type, amount, description, timestamp FROM transaction_history WHERE account_id = :aid ORDER BY timestamp DESC"
    rows = await database.fetch_all(q, values={"aid": str(account_id)})
    return [dict(r) for r in rows]


@router.get("/accounts/{account_id}/events")
async def get_account_events(account_id: str):
    # audit endpoint: read from events store
    q = "SELECT event_id, event_number, event_type, event_data, timestamp FROM events WHERE aggregate_id = :aid ORDER BY event_number ASC"
    rows = await database.fetch_all(q, values={"aid": str(account_id)})
    return [dict(r) for r in rows]
