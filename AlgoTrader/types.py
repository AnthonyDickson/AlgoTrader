import enum
from typing import NewType

PortfolioID = NewType('PortfolioID', int)
Ticker = NewType('Ticker', str)
PositionID = NewType('PositionID', int)


# TODO: Grab these from the server.
class TransactionType(enum.Enum):
    DEPOSIT = enum.auto()
    WITHDRAWAL = enum.auto()
    BUY = enum.auto()
    SELL = enum.auto()
    DIVIDEND = enum.auto()
    CASH_SETTLEMENT = enum.auto()
