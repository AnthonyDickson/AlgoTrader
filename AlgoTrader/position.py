import datetime
import sqlite3
from typing import Tuple, Optional

from AlgoTrader.types import PortfolioID, Ticker, PositionID


# TODO: Sync state with database.
# TODO: Use database data to calculate stats.
class Position:

    def __init__(self, portfolio_id: PortfolioID, ticker: Ticker,
                 entry_price: float, quantity: int,
                 open_timestamp: datetime.datetime,
                 db_connection: Optional[sqlite3.Connection],
                 position_id: Optional[PositionID] = None):
        """
        Enter a new position (buy an amount of a security).

        Notes:
        - Only one of `db_connection` or `position_id` must be specified.
        - The `position_id` argument is mainly for batch operations and internal use. If you are creating a single
        position, or creating positions infrequently, using the `db_connection` argument so the ID can be inferred will
        likely result in less rows inserted with duplicate primary keys and less bugs in your code.

        :param portfolio_id: The portfolio this position will belong to.
        :param ticker: The ticker of the security that is being bought.
        :param entry_price: The current price of the security.
        :param quantity: How many shares of the security that is being bought.
        :param open_timestamp: When this position is being opened.
        :param db_connection: (optional) A connection to a database that can be queried for data on positions.
        :param position_id: (optional) The pre-determined ID of the position.
        """
        assert quantity >= 1, 'Cannot open a position with less than one share.'
        assert (db_connection is not None and position_id is None) or \
               (db_connection is None and position_id is not None), \
            "You must specify only one of 'db_connection' or 'position_id', not both nor neither."

        self._portfolio_id = portfolio_id
        self.ticker: Ticker = ticker
        self._quantity: int = quantity
        self._entry_price: float = entry_price
        self._exit_price: float = 0.0
        self._opened_timestamp: datetime.datetime = open_timestamp
        self._closed_timestamp: Optional[datetime.datetime] = None
        self._dividends_received = 0.00
        self._cash_settlements_received = 0.00
        self.is_closed: bool = False

        if db_connection is not None:
            with db_connection:
                cursor = db_connection.execute(
                    "INSERT INTO position (portfolio_id, ticker) VALUES (?, ?)",
                    (self.portfolio_id, self.ticker,)
                )

                self._id = PositionID(cursor.lastrowid)
                cursor.close()
        else:
            self._id = PositionID(position_id)

    @property
    def id(self) -> PositionID:
        return self._id

    @property
    def portfolio_id(self) -> PortfolioID:
        """Get the ID of the portfolio that this position belongs to."""
        return self._portfolio_id

    @property
    def opened_timestamp(self) -> datetime.datetime:
        """The period_end indicating when this position was opened."""
        return self._opened_timestamp

    @property
    def closed_timestamp(self) -> Optional[datetime.datetime]:
        """
        The period_end indicating when this position was closed.
        Note: This will be None if the position is still open.
        """
        return self._closed_timestamp

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
        return (self.exit_value - self.entry_value) + self.cash_settlements_received

    def unrealised_pl(self, current_price) -> float:
        """
        Calculate the unrealised profit and loss of the position.
        This is equal to the current value of the position minus the total cost.
        :param current_price: The current price of the security this position is invested in.
        :return: the unrealised profit and loss of the position
        """
        return self._quantity * (current_price - self._entry_price)

    def current_value(self, current_price) -> float:
        """
        Calculate the current value of the position. This is equal to the current price of the security multiplied by
        the number of shares that this position is invested in.
        :param current_price: The current price of the security that this position is invested in.
        :return: the current value of the position.
        """
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

    def close(self, price: float, timestamp: datetime.datetime) -> float:
        """
        Close this position.

        :param price: The price of the security that this position is invested in at the time of closing.
        :param timestamp: The time (and date) that the position is being closed at.
        :return: The value that the position closed at.
        """
        assert self.is_closed is not True, "Attempt to close a position that has already been closed."

        self._exit_price = price
        self.is_closed = True
        self._closed_timestamp = timestamp

        return self.exit_value

    def __repr__(self):
        return (f'{self.__class__.__name__}(ticker={self.ticker}, entry_price={self.entry_price}, '
                f'quantity={self.quantity})')
