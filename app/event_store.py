import json
from typing import List, Dict, Any, Optional
from .main import database


async def get_last_sequence(aggregate_id: str) -> int:
    q = "SELECT COALESCE(MAX(event_number), 0) AS seq FROM events WHERE aggregate_id = :aid"
    r = await database.fetch_one(q, values={"aid": str(aggregate_id)})
    return int(r["seq"] or 0)


async def append_events(aggregate_id: str, aggregate_type: str, events: List[Dict[str, Any]], metadata: Optional[Dict[str, Any]] = None):
    # events: list of {event_type: str, event_data: dict}
    last_seq = await get_last_sequence(aggregate_id)
    inserted = []
    async with database.transaction():
        for idx, ev in enumerate(events, start=1):
            seq = last_seq + idx
            q = """
            INSERT INTO events (aggregate_id, aggregate_type, event_type, event_data, event_number, version)
            VALUES (:aggregate_id, :aggregate_type, :event_type, :event_data::jsonb, :event_number, :version)
            RETURNING event_id, event_number, timestamp
            """
            values = {
                "aggregate_id": str(aggregate_id),
                "aggregate_type": aggregate_type,
                "event_type": ev["event_type"],
                "event_data": json.dumps(ev.get("event_data", {})),
                "event_number": seq,
                "version": ev.get("version", 1),
            }
            row = await database.fetch_one(q, values=values)
            inserted.append({"event_id": str(row["event_id"]), "event_number": row["event_number"], "event_type": ev["event_type"], "event_data": ev.get("event_data", {}), "timestamp": row["timestamp"]})
    return inserted


async def load_events(aggregate_id: str, from_number: int = 0):
    q = "SELECT event_id, event_number, event_type, event_data, timestamp FROM events WHERE aggregate_id = :aid AND event_number > :from_num ORDER BY event_number ASC"
    rows = await database.fetch_all(q, values={"aid": str(aggregate_id), "from_num": from_number})
    result = []
    for r in rows:
        result.append({
            "event_id": str(r["event_id"]),
            "event_number": r["event_number"],
            "event_type": r["event_type"],
            "event_data": r["event_data"],
            "timestamp": r["timestamp"],
        })
    return result


async def create_snapshot(aggregate_id: str, snapshot_sequence: int, snapshot_data: Dict[str, Any]):
    # upsert snapshot row for aggregate
    q = """
    INSERT INTO snapshots (aggregate_id, snapshot_data, last_event_number)
    VALUES (:aid, :sdata::jsonb, :last)
    ON CONFLICT (aggregate_id) DO UPDATE SET snapshot_data = EXCLUDED.snapshot_data, last_event_number = EXCLUDED.last_event_number, created_at = now()
    """
    await database.execute(q, values={"aid": str(aggregate_id), "sdata": json.dumps(snapshot_data), "last": snapshot_sequence})


async def load_latest_snapshot(aggregate_id: str):
    q = "SELECT last_event_number, snapshot_data, created_at FROM snapshots WHERE aggregate_id = :aid LIMIT 1"
    r = await database.fetch_one(q, values={"aid": str(aggregate_id)})
    if not r:
        return None
    return {"last_event_number": int(r["last_event_number"]), "snapshot_data": r["snapshot_data"], "created_at": r["created_at"]}
