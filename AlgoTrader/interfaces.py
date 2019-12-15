import abc

from AlgoTrader.portfolio import Portfolio


# noinspection PyUnusedLocal
class ITradingBot(abc.ABC):
    def __init__(self, initial_portfolio: Portfolio, git_hash: str = 'infer'):
        """
        Create a new bot.
        :param initial_portfolio: The portfolio that the bot starts with.
        :param git_hash: The
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
    def portfolio(self) -> Portfolio:
        """Get the bot's portfolio."""
        raise NotImplementedError
