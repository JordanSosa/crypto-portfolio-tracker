"""
Transaction Models
Data models for transaction tracking, cost basis, and P&L calculations
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional
from enum import Enum


class TransactionType(Enum):
    """Type of transaction"""
    BUY = "BUY"
    SELL = "SELL"


class AccountingMethod(Enum):
    """Accounting method for cost basis calculation"""
    FIFO = "FIFO"  # First In, First Out
    LIFO = "LIFO"  # Last In, First Out
    AVERAGE_COST = "AVERAGE_COST"
    SPECIFIC_ID = "SPECIFIC_ID"


@dataclass
class Transaction:
    """Represents a single buy or sell transaction"""
    id: Optional[int] = None
    timestamp: Optional[datetime] = None
    symbol: str = ""
    transaction_type: TransactionType = TransactionType.BUY
    amount: float = 0.0
    price_per_unit: float = 0.0
    total_value: float = 0.0
    fee: float = 0.0
    fee_currency: str = "AUD"
    exchange: Optional[str] = None
    transaction_id: Optional[str] = None
    notes: Optional[str] = None


@dataclass
class CostBasisLot:
    """Represents a purchase lot for cost basis tracking"""
    id: Optional[int] = None
    transaction_id: int = 0
    symbol: str = ""
    amount: float = 0.0
    cost_per_unit: float = 0.0
    total_cost: float = 0.0
    fee: float = 0.0
    purchase_date: Optional[datetime] = None
    is_closed: bool = False
    closed_date: Optional[datetime] = None


@dataclass
class RealizedPnL:
    """Represents a realized gain/loss from closing a position"""
    id: Optional[int] = None
    sell_transaction_id: int = 0
    lot_id: int = 0
    symbol: str = ""
    amount: float = 0.0
    cost_basis: float = 0.0
    sale_price: float = 0.0
    sale_value: float = 0.0
    realized_gain_loss: float = 0.0
    accounting_method: AccountingMethod = AccountingMethod.FIFO
    sale_date: Optional[datetime] = None


@dataclass
class UnrealizedPnL:
    """Represents unrealized gain/loss on current holdings"""
    symbol: str
    current_amount: float
    average_cost_basis: float
    current_price: float
    total_cost_basis: float
    current_value: float
    unrealized_gain_loss: float
    unrealized_gain_loss_pct: float

