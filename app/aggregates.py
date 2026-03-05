from decimal import Decimal


class BankAccount:
    def __init__(self, account_id):
        self.account_id = account_id
        self.owner_name = None
        self.balance = Decimal("0.00")
        self.status = "active"
        self.last_sequence = 0

    def apply(self, event):
        et = event.get("event_type")
        data = event.get("event_data") or {}
        seq = event.get("event_number") or 0
        if et == "AccountCreated":
            self.owner_name = data.get("ownerName") or data.get("owner_name")
            self.balance = Decimal(str(data.get("initialBalance", data.get("initial_balance", 0))))
            self.status = "OPEN"
        elif et == "MoneyDeposited":
            amt = Decimal(str(data.get("amount")))
            self.balance += amt
        elif et == "MoneyWithdrawn":
            amt = Decimal(str(data.get("amount")))
            self.balance -= amt
        elif et == "AccountClosed":
            self.status = "CLOSED"

        self.last_sequence = seq


    @classmethod
    def from_events(cls, account_id, events):
        acc = cls(account_id)
        for e in events:
            acc.apply(e)
        return acc

    @classmethod
    def from_snapshot(cls, account_id, snapshot_data: dict, snapshot_sequence: int = 0):
        acc = cls(account_id)
        if snapshot_data:
            acc.owner_name = snapshot_data.get("ownerName") or snapshot_data.get("owner_name")
            acc.balance = Decimal(str(snapshot_data.get("balance", "0.00")))
            acc.status = snapshot_data.get("status", "OPEN")
            acc.last_sequence = int(snapshot_sequence or 0)
        return acc

    def to_snapshot(self) -> dict:
        return {"ownerName": self.owner_name, "balance": float(self.balance), "status": self.status}
