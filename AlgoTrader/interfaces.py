import abc
import datetime
from typing import Optional, Iterable, Set

from AlgoTrader.broker import Broker
from AlgoTrader.types import PortfolioID, Ticker


# noinspection PyUnusedLocal
class ITradingBot(abc.ABC):
    def __init__(self, broker: Broker, tickers: Iterable[Ticker]):
        """
        Create a new bot.

        :param broker: The broker that will facilitate trades.
        :param tickers: The tickers that this bot should trade in.
        """
        ...

    def update(self, today: datetime.datetime):
        """
        Perform an update step where the bot may or may not open or close positions.

        :param today: Today's date.
        """
        raise NotImplementedError

    @property
    def tickers(self) -> Set[Ticker]:
        """Get the set of tickers that this bot trades in."""
        raise NotImplementedError

    @property
    def portfolio_id(self) -> Optional[PortfolioID]:
        """Get the bot's current portfolio's ID."""
        raise NotImplementedError

    @portfolio_id.setter
    def portfolio_id(self, value: PortfolioID):
        """
        Set the bot's current portfolio ID.
        This will affect which portfolio the bot will use for any future trades.
        """
        raise NotImplementedError

    @property
    def name(self) -> str:
        """Get the name of the bot."""
        raise NotImplementedError
