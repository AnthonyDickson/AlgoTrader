import sqlite3
from typing import Tuple

from AlgoTrader.types import PortfolioID, Ticker, PositionID


# TODO: Sync state with database.
# TODO: Use database data to calculate stats.
class Position:

    def __init__(self, portfolio_id: PortfolioID, ticker: Ticker, entry_price: float, quantity: int,
                 db_connection: sqlite3.Connection):
        """
        Enter a new position (buy an amount of a security).

        :param portfolio_id: The portfolio this position will belong to.
        :param ticker: The ticker of the security that is being bought.
        :param entry_price: The current price of the security.
        :param quantity: How many shares of the security that is being bought.
        :param db_connection: A connection to a database that can be queried for data on positions.
        """
        assert quantity >= 1, 'Cannot open a position with less than one share.'

        self._portfolio_id = portfolio_id
        self._ticker: Ticker = ticker
        self._quantity: int = quantity
        self._entry_price: float = entry_price
        self._exit_price: float = 0.0
        self._dividends_received = 0.00
        self._cash_settlements_received = 0.00
        self._pl_realised: float = 0.0
        self._pl_unrealised: float = 0.0
        self._is_closed: bool = False

        self.db_cursor = db_connection.cursor()
        self.db_cursor.execute(
            "INSERT INTO position (portfolio_id, ticker) VALUES (?, ?)",
            (self.portfolio_id, self.ticker,)
        )

        self._id = PositionID(self.db_cursor.lastrowid)

        self.db_cursor.connection.commit()

    def __del__(self):
        try:
            self.db_cursor.close()
        except sqlite3.ProgrammingError:
            pass

    @property
    def id(self) -> PositionID:
        return self._id

    @property
    def portfolio_id(self) -> PortfolioID:
        """Get the ID of the portfolio that this position belongs to."""
        return self._portfolio_id

    @property
    def ticker(self) -> Ticker:
        """The ticker of the security that this position is invested in."""
        return self._ticker

    @property
    def is_closed(self) -> bool:
        """ Whether the position is closed or not (i.e. still open).
        """
        return self._is_closed

    @property
    def entry_price(self) -> float:
        """The price per share when the position was opened."""
        return self._entry_price

    @property
    def quantity(self):
        """The number of shares purchased for this position."""
        return self._quantity

    @property
    def entry_value(self) -> float:
        """The value of the position when it was opened."""
        return self._quantity * self._entry_price

    @property
    def cost(self) -> float:
        """How much the position cost to open."""
        return self.entry_value

    @property
    def exit_value(self) -> float:
        """The value of the position when it was closed."""
        assert self.is_closed, 'Cannot get the exit value of a position that is still open.'

        return self.quantity * self._exit_price

    @property
    def dividends_received(self) -> float:
        """How much this position has earned in dividends."""
        return self._dividends_received

    @dividends_received.setter
    def dividends_received(self, value: float):
        self._dividends_received = value

    @property
    def cash_settlements_received(self) -> float:
        """How much this position has received in cash settlements."""
        return self._cash_settlements_received

    @cash_settlements_received.setter
    def cash_settlements_received(self, value: float):
        """How much this position has received in cash settlements."""
        self._cash_settlements_received = value

    @property
    def adjustments(self) -> float:
        """How much this position has received in dividends and cash settlements."""
        return self.dividends_received + self.cash_settlements_received

    @property
    def realised_pl(self) -> float:
        """The realised profit and loss of the position."""
        return self._pl_realised + self.cash_settlements_received

    def unrealised_pl(self, current_price) -> float:
        """
        Calculate the unrealised profit and loss of the position.
        This is equal to the current value of the position minus the total cost.
        :param current_price: The current price of the security this position is invested in.
        :return: the unrealised profit and loss of the position
        """
        assert self.is_closed is False, \
            'Cannot get the unrealised P&L of a closed position. Use `pl_realised()` instead.'

        self._pl_unrealised = self._quantity * (current_price - self._entry_price)

        return self._pl_unrealised

    def current_value(self, current_price) -> float:
        """
        Calculate the current value of the position. This is equal to the current price of the security multiplied by
        the number of shares that this position is invested in.
        :param current_price: The current price of the security that this position is invested in.
        :return: the current value of the position.
        """
        assert self.is_closed is False, 'Cannot check current value on a closed position, use `exit_value` instead.'

        return self.quantity * current_price

    def adjust_for_dividend(self, dividend_per_share: float):
        """
        Adjust the position value according to a given dividend amount.

        :param dividend_per_share: The dividend per share.
        :return: The total dividend this position is entitled to (quantity * dividend_amount).
        """
        assert dividend_per_share > 0, f'Cannot pay a non-positive dividend of {dividend_per_share}.'

        total_dividend_amount = self.quantity * dividend_per_share
        self._dividends_received += total_dividend_amount

        return total_dividend_amount

    # TODO: Write unit tests for this... and other stuff while I am at it...
    def adjust_for_stock_split(self, split_coefficient: float) -> Tuple[float, float, float, float]:
        """
        Adjust this position for a stock split.

        Note:
        - If a split results in a position with a fractional share, the fractional share is compensated with a cash
          settlement of equal value.

        :param split_coefficient: The ratio of shares each pre-split share is now worth.
        :return: A 3-tuple containing: number of whole shares, amount of fractional shares, the adjusted share price
        and cash settlement amount (this may be zero).
        """
        assert not self.is_closed, 'Cannot adjust a closed position for stock split.'

        whole_shares, fractional_shares = divmod(self.quantity * split_coefficient, 1.0)
        adjusted_price = self.entry_price / split_coefficient
        cash_settlement_amount = fractional_shares * adjusted_price
        self._cash_settlements_received += cash_settlement_amount

        return whole_shares, fractional_shares, adjusted_price, cash_settlement_amount

    def close(self, price: float) -> float:
        """
        Close this position.

        :param price: The price of the security that this position is invested in at the time of closing.
        :return: The value that the position closed at.
        """
        assert self._is_closed is not True, "Attempt to close a position that has already been closed."

        self._exit_price = price
        self._pl_realised = self._quantity * (self._exit_price - self._entry_price)
        self._pl_unrealised = 0.0
        self._is_closed = True

        return self.exit_value

    def __repr__(self):
        return (f'{self.__class__.__name__}(ticker={self._ticker}, entry_price={self.entry_price}, '
                f'quantity={self.quantity})')
