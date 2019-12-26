import datetime
import enum
from typing import NewType, Tuple, Callable

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
    TAX = enum.auto()


BuyOrder = Tuple[PortfolioID, Ticker, int, float, datetime.datetime]
Transaction = Tuple[PortfolioID, PositionID, TransactionType, int, float, datetime.datetime]


@enum.unique
class Period(enum.Enum):
    DAILY = enum.auto()
    WEEKLY = enum.auto()
    MONTHLY = enum.auto()
    QUARTERLY = enum.auto()
    YEARLY = enum.auto()


"""A function that takes a portfolio balance and market price of a share, and determines the number of shares to buy."""
BuyQuantityFunc = Callable[[float, float], int]
"""
A function that takes the market value and purchase value of a position, and determines if the position should be sold.
"""
ShouldSellFunc = Callable[[float, float], bool]
