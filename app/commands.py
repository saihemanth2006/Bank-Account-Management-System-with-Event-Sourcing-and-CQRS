from fastapi import APIRouter, HTTPException
from fastapi import APIRouter, HTTPException, status
from uuid import uuid4
from decimal import Decimal
from typing import Optional
from .schemas import CreateAccountCommand, MoneyCommand
from .event_store import load_events, append_events, get_last_sequence, load_latest_snapshot, create_snapshot
from .aggregates import BankAccount
from .main import database
from . import projections as proj

router = APIRouter()


@router.post("/accounts", status_code=status.HTTP_202_ACCEPTED)
async def create_account(cmd: CreateAccountCommand):
    account_id = cmd.accountId or str(uuid4())
    # Ensure account doesn't already exist
    existing = await load_events(account_id)
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Account already exists")

    ev = {"event_type": "AccountCreated", "event_data": {"ownerName": cmd.ownerName, "initialBalance": float(cmd.initialBalance or 0), "currency": cmd.currency}}
    inserted = await append_events(account_id, "BankAccount", [ev])
    # process projections synchronously
    for e in inserted:
        await proj.process_event(account_id, e)
    # Snapshotting: create snapshot every 50 events
    last_seq = await get_last_sequence(account_id)
    if last_seq > 0 and last_seq % 50 == 0:
        snap = await load_latest_snapshot(account_id)
        start_seq = snap["last_event_number"] if snap else 0
        events_to_apply = await load_events(account_id, from_number=start_seq)
        if snap:
            acc = BankAccount.from_snapshot(account_id, snap.get("snapshot_data"), snap.get("last_event_number"))
        else:
            acc = BankAccount(account_id)
        for ev2 in events_to_apply:
            acc.apply(ev2)
        await create_snapshot(account_id, last_seq, acc.to_snapshot())
    return {"accountId": account_id, "events": inserted}


@router.post("/accounts/{account_id}/deposit", status_code=status.HTTP_202_ACCEPTED)
async def deposit_money(account_id: str, cmd: MoneyCommand):
    # require transactionId for idempotency
    if not cmd.transactionId:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="transactionId is required")
    # idempotency: if transaction exists, return accepted
    exists_tx = await database.fetch_one("SELECT 1 FROM transaction_history WHERE transaction_id = :tid", values={"tid": cmd.transactionId})
    if exists_tx:
        return {"status": "accepted", "transactionId": cmd.transactionId}

    events = await load_events(account_id)
    if not events:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found")
    acc = BankAccount.from_events(account_id, events)
    if acc.status != "active" and acc.status != "OPEN":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Account not active")
    amt = Decimal(cmd.amount)
    if amt <= 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Amount must be positive")

    ev = {"event_type": "MoneyDeposited", "event_data": {"amount": float(amt), "description": cmd.description, "transactionId": cmd.transactionId}}
    inserted = await append_events(account_id, "BankAccount", [ev])
    for e in inserted:
        await proj.process_event(account_id, e)
    last_seq = await get_last_sequence(account_id)
    if last_seq > 0 and last_seq % 50 == 0:
        snap = await load_latest_snapshot(account_id)
        start_seq = snap["last_event_number"] if snap else 0
        events_to_apply = await load_events(account_id, from_number=start_seq)
        acc = BankAccount.from_snapshot(account_id, snap.get("snapshot_data"), snap.get("last_event_number")) if snap else BankAccount(account_id)
        for ev2 in events_to_apply:
            acc.apply(ev2)
        await create_snapshot(account_id, last_seq, acc.to_snapshot())
    return {"status": "accepted", "events": inserted}


@router.post("/accounts/{account_id}/withdraw", status_code=status.HTTP_202_ACCEPTED)
async def withdraw_money(account_id: str, cmd: MoneyCommand):
    if not cmd.transactionId:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="transactionId is required")
    exists_tx = await database.fetch_one("SELECT 1 FROM transaction_history WHERE transaction_id = :tid", values={"tid": cmd.transactionId})
    if exists_tx:
        return {"status": "accepted", "transactionId": cmd.transactionId}
    events = await load_events(account_id)
    if not events:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found")
    acc = BankAccount.from_events(account_id, events)
    if acc.status != "active" and acc.status != "OPEN":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Account not active")
    amt = Decimal(cmd.amount)
    if amt <= 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Amount must be positive")
    if amt > acc.balance:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Insufficient funds")

    ev = {"event_type": "MoneyWithdrawn", "event_data": {"amount": float(amt), "description": cmd.description, "transactionId": cmd.transactionId}}
    inserted = await append_events(account_id, "BankAccount", [ev])
    for e in inserted:
        await proj.process_event(account_id, e)
    last_seq = await get_last_sequence(account_id)
    if last_seq > 0 and last_seq % 50 == 0:
        snap = await load_latest_snapshot(account_id)
        start_seq = snap["last_event_number"] if snap else 0
        events_to_apply = await load_events(account_id, from_number=start_seq)
        acc = BankAccount.from_snapshot(account_id, snap.get("snapshot_data"), snap.get("last_event_number")) if snap else BankAccount(account_id)
        for ev2 in events_to_apply:
            acc.apply(ev2)
        await create_snapshot(account_id, last_seq, acc.to_snapshot())
    return {"status": "accepted", "events": inserted}


@router.post("/accounts/{account_id}/close", status_code=status.HTTP_202_ACCEPTED)
async def close_account(account_id: str):
    events = await load_events(account_id)
    if not events:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found")
    acc = BankAccount.from_events(account_id, events)
    if acc.balance != Decimal("0.00"):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Account balance must be zero to close")
    if acc.status == "closed" or acc.status == "CLOSED":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Account already closed")

    ev = {"event_type": "AccountClosed", "event_data": {}}
    inserted = await append_events(account_id, "BankAccount", [ev])
    for e in inserted:
        await proj.process_event(account_id, e)
    last_seq = await get_last_sequence(account_id)
    if last_seq > 0 and last_seq % 50 == 0:
        snap = await load_latest_snapshot(account_id)
        start_seq = snap["last_event_number"] if snap else 0
        events_to_apply = await load_events(account_id, from_number=start_seq)
        acc = BankAccount.from_snapshot(account_id, snap.get("snapshot_data"), snap.get("last_event_number")) if snap else BankAccount(account_id)
        for ev2 in events_to_apply:
            acc.apply(ev2)
        await create_snapshot(account_id, last_seq, acc.to_snapshot())
    return {"status": "accepted", "events": inserted}
        last_seq = await get_last_sequence(account_id)
        if last_seq > 0 and last_seq % 50 == 0:
            snap = await load_latest_snapshot(account_id)
            start_seq = snap["last_event_number"] if snap else 0
            events_to_apply = await load_events(account_id, from_number=start_seq)
            acc = BankAccount.from_snapshot(account_id, snap.get("snapshot_data"), snap.get("last_event_number")) if snap else BankAccount(account_id)
            for ev2 in events_to_apply:
                acc.apply(ev2)
            await create_snapshot(account_id, last_seq, acc.to_snapshot())
        return {"status": "accepted", "events": inserted}


    @router.post("/accounts/{account_id}/close", status_code=status.HTTP_202_ACCEPTED)
    async def close_account(account_id: str):
        events = await load_events(account_id)
        if not events:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found")
        acc = BankAccount.from_events(account_id, events)
        if acc.balance != Decimal("0.00"):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Account balance must be zero to close")
        if acc.status == "closed" or acc.status == "CLOSED":
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Account already closed")

        ev = {"event_type": "AccountClosed", "event_data": {}}
        inserted = await append_events(account_id, "BankAccount", [ev])
        for e in inserted:
            await proj.process_event(account_id, e)
        last_seq = await get_last_sequence(account_id)
        if last_seq > 0 and last_seq % 50 == 0:
            snap = await load_latest_snapshot(account_id)
            start_seq = snap["last_event_number"] if snap else 0
            events_to_apply = await load_events(account_id, from_number=start_seq)
            acc = BankAccount.from_snapshot(account_id, snap.get("snapshot_data"), snap.get("last_event_number")) if snap else BankAccount(account_id)
            for ev2 in events_to_apply:
                acc.apply(ev2)
            await create_snapshot(account_id, last_seq, acc.to_snapshot())
        return {"status": "accepted", "events": inserted}
