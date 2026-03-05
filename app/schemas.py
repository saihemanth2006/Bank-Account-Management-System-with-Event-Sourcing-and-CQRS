from pydantic import BaseModel, Field
from typing import Optional, List
from uuid import UUID
from decimal import Decimal


class CreateAccountCommand(BaseModel):
    accountId: Optional[str]
    ownerName: str
    initialBalance: Optional[Decimal] = Decimal("0.00")
    currency: Optional[str] = "USD"


class MoneyCommand(BaseModel):
    amount: Decimal = Field(..., gt=0)
    description: Optional[str]
    transactionId: Optional[str]


class AccountSummary(BaseModel):
    accountId: str
    ownerName: Optional[str]
    balance: Decimal
    currency: str
    status: str
    version: int


class TransactionItem(BaseModel):
    transactionId: str
    accountId: str
    type: str
    amount: Decimal
    description: Optional[str]
    timestamp: str
