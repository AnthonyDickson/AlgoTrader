import abc
from typing import Optional

from AlgoTrader.broker import Broker
from AlgoTrader.types import PortfolioID


# noinspection PyUnusedLocal
class ITradingBot(abc.ABC):
    def __init__(self, broker: Broker):
        """
        Create a new bot.

        :param broker: The broker that will facilitate trades.
        """
        ...

    def update(self, ticker, datum, prev_datum):
        """
        Perform an update step where the bot may or may not open or close positions.
        :param ticker: The ticker of the security to focus on.
        :param datum: The data for the given ticker for a given day. This should include both close prices and
        MACD information.
        :param prev_datum: The data for the given ticker for the previous day.
        """
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
