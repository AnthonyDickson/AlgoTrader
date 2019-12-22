import datetime
import sqlite3
from typing import Set, Optional

from AlgoTrader.exceptions import InsufficientFundsError
from AlgoTrader.position import Position
from AlgoTrader.types import PortfolioID, Ticker, TransactionType


# TODO: Sync state with database.
class Portfolio:

    def __init__(self, owner_name: str, timestamp: datetime.datetime,
                 db_connection: sqlite3.Connection):
        self._balance: float = 0.0
        self._contribution: float = 0.0
        self._created_timestamp: datetime.datetime = timestamp
        self._positions: Set[Position] = set()
        self._open_positions: Set[Position] = set()
        self._tickers: Set[Ticker] = set()

        self._owner_name = owner_name

        self.db_connection = db_connection

        with self.db_connection:
            cursor = self.db_connection.execute('''
                    INSERT INTO portfolio (owner_name) VALUES (?)
                    ''', (self._owner_name,))

            self._id = PortfolioID(cursor.lastrowid)
            cursor.close()

    @property
    def id(self) -> PortfolioID:
        return self._id

    @property
    def tickers(self) -> Set[Ticker]:
        """The set of tickers of the positions in this portfolio."""
        return self._tickers

    @property
    def contribution(self):
        """
        The amount of cash that has been added to the portfolio
        (e.g. the user transferring money into their brokerage account).
        """
        return self._contribution

    @property
    def balance(self) -> float:
        """The available amount of cash."""
        return self._balance

    @property
    def positions(self) -> Set[Position]:
        """The list of positions (both open and closed) in this portfolio."""
        return self._positions.copy()

    @property
    def open_positions(self) -> Set[Position]:
        """The list of open positions in this portfolio."""
        return self._open_positions.copy()

    def sync(self):
        """Sync the portfolio data with the database."""
        cursor = self.db_connection.execute(
            '''SELECT balance FROM portfolio_balance WHERE portfolio_id = ?''',
            (self.id,)
        )

        new_balance = cursor.fetchone()['balance']
        cursor.close()

        # TODO: Fix database and local balances diverging due to different floating point precision...
        # assert abs(self._balance - new_balance) < sys.float_info.epsilon, \
        #     f"Balances do not match: expected {new_balance}, but got {self._balance}"

        self._balance = new_balance

    def open_position(self, ticker: Ticker, price: float, quantity: int,
                      timestamp: datetime.datetime) -> Position:
        """
        Open a position and add it to this portfolio.

        :param ticker: The ticker of the security that is being bought.
        :param price: The current price of the security.
        :param quantity: How many shares of the security that is being bought.
        :param timestamp: When the position is being opened.
        :return: The opened position.
        :raises InsufficientFundsError: if there is not enough funds to open the given position.
        """
        # Deduct cost first to ensure that the account has enough funds (it will raise an exception if it doesn't).
        self._deduct(price * quantity)

        position = Position(self.id, ticker, price, quantity, timestamp,
                            self.db_connection)

        self._tickers.add(position.ticker)
        self._positions.add(position)
        self._open_positions.add(position)

        return position

    def close_position(self, position: Position, price: float,
                       timestamp: datetime.datetime):
        """
        Close the given position at the given price.
        :param position: The position to close.
        :param price: The current price of the security the position covers.
        :param timestamp: When the position is being closed.
        :raises AssertionError: if the position was not added to the portfolio.
        """
        assert position in self.positions, 'Cannot close a position that does not belong to this portfolio.'

        self._balance += position.close(price, timestamp)
        self._open_positions.discard(position)

    # TODO: Only use transactions up to and including given date when giving report.
    def print_summary(self, period_end: datetime.datetime,
                      period_start: Optional[datetime.datetime] = None):
        """
        Print a summary of the portfolio.
        :param period_end: The last date that is included in the reporting period.
        :param period_start: (optional) The first date that is included in the reporting period. If not specified, then
        the created_timestamp for when the portfolio was created will be used.
        """
        print(PortfolioSummary(self, self.db_connection, period_end, period_start))

    def deposit(self, amount: float):
        """
        Add an amount of cash to the balance of this portfolio as an contribution
        (i.e. the owner adds money to their account themselves).

        :param amount: The amount to add to the portfolio.
        """
        self._pay(amount)
        self._contribution += amount

    def withdraw(self, amount: float):
        """
        Withdraw funds from the portfolio account.

        :param amount: The amount to withdraw.
        """
        self._deduct(amount)

    def pay_dividend(self, amount: float, position: Position):
        """
        Pay a dividend to this portfolio.

        :param position: The position that the dividend is being paid for.
        :param amount: The amount to be paid per share.
        """
        total_dividend_amount = position.adjust_for_dividend(amount)
        self._pay(total_dividend_amount)

    def pay_cash_settlement(self, amount: float, position):
        """
        Pay a cash settlement resulting from a stock split to this portfolio.

        :param position: The position that the cash settlement is being paid for.
        :param amount: The amount to be paid.
        """
        self._pay(amount)
        position.cash_settlements_received += amount

    def _pay(self, amount: float):
        """
        Add an amount of cash to the balance of this portfolio.

        :param amount: The amount to add to the portfolio.
        """
        if amount < 0:
            raise ValueError(f'Cannot add negative amount {amount} to balance.')
        elif amount > 0:
            self._balance += amount
            self.should_fetch_new_balance = True

    def _deduct(self, amount: float):
        """
        Deduct an amount of cash to the balance of this portfolio.

        :param amount: The amount to deduct from the portfolio.
        """
        if amount > self.balance:
            raise InsufficientFundsError(f"Not enough funds to deduct {amount}.")
        else:
            self._balance -= amount

    @property
    def created_timestamp(self):
        return self._created_timestamp


# TODO: Update to use data from database.
# TODO: Calculate unrealised and net p&L using transaction data.
# TODO: Upload reports to database.
# TODO: Include YoY P&L - this can be done by reading transaction data.
class PortfolioSummary:
    """Summary report of the performance of the portfolio."""

    def __init__(self, portfolio: Portfolio, db_connection: sqlite3.Connection, period_end: datetime.datetime,
                 period_start: Optional[datetime.datetime] = None):
        """
        Create a summary report of a portfolio.
        :param portfolio: The portfolio to report on.
        :param db_connection: A database connection that can be used to query for stock price and transaction data.
        :param period_end: The lsat date that is included in the reporting period.
        :param period_start: (optional) The first date that is included in the reporting period. If not specified, then
        the created_timestamp for when the portfolio was created will be used.
        """
        if period_start is None:
            period_start = portfolio.created_timestamp

        cursor = db_connection.execute(
            f'''
            SELECT ticker, close, MAX(datetime)
            FROM daily_stock_data
            WHERE ? <= datetime AND datetime <= ?
            GROUP BY ticker;
            ''',
            (period_start, period_end,)
        )

        stock_prices = {row['ticker']: row['close'] for row in cursor}
        cursor.close()

        self.total_deposits: float = 0.0
        self.total_withdrawals: float = 0.0
        self.total_dividends_received: float = 0.0
        self.total_cash_settlements_received: float = 0.0

        cursor = db_connection.execute(
            f"""
            SELECT type, SUM(price * quantity) AS total
            FROM transactions 
            WHERE portfolio_id = ? AND ? <= timestamp AND timestamp <= ? AND type IN (?, ?, ?, ?)
            GROUP BY type;
            """,
            (portfolio.id, period_start, period_end,
             TransactionType.DEPOSIT.value, TransactionType.WITHDRAWAL.value,
             TransactionType.DIVIDEND.value, TransactionType.CASH_SETTLEMENT.value)
        )

        for row in cursor:
            if row['type'] == TransactionType.DEPOSIT.value:
                self.total_deposits = row['total']
            elif row['type'] == TransactionType.WITHDRAWAL.value:
                self.total_withdrawals = row['total']
            elif row['type'] == TransactionType.DIVIDEND.value:
                self.total_dividends_received = row['total']
            elif row['type'] == TransactionType.CASH_SETTLEMENT.value:
                self.total_cash_settlements_received = row['total']
            else:
                raise ValueError(f"Got unexpected type from totals query: {row['type']}.")

        cursor.close()

        self.date_created = portfolio.created_timestamp
        self.period_start = period_start
        self.period_end = period_end
        self.portfolio_age: float = (self.period_end - self.date_created).days / 365.25

        self.total_num_closed_positions: float = 0.0
        self.total_num_open_positions: float = 0.0
        self.total_closed_position_cost: float = 0.0
        self.total_closed_position_value: float = 0.0
        self.realised_pl: float = 0.0
        self.total_num_closed_positions: float = 0.0
        self.total_open_position_cost: float = 0.0
        self.total_open_position_value: float = 0.0
        self.unrealised_pl: float = 0.0

        for position in portfolio.positions:
            if not position.is_closed and position.opened_timestamp >= self.period_start:
                self.total_num_open_positions += 1
                self.total_open_position_cost += position.cost

                try:
                    stock_price = stock_prices[position.ticker]

                    self.total_open_position_value += position.current_value(stock_price)
                    self.unrealised_pl += position.unrealised_pl(stock_price)
                except KeyError:
                    print(f'WARNING: Missing stock prices for {position.ticker}.')
            elif position.is_closed and position.closed_timestamp <= self.period_end:
                self.total_num_closed_positions += 1
                self.total_closed_position_cost += position.cost
                self.total_closed_position_value += position.exit_value
                self.realised_pl += position.realised_pl

        self.total_num_positions = self.total_num_open_positions + self.total_num_closed_positions
        self.total_position_cost = self.total_open_position_cost + self.total_closed_position_cost
        self.total_position_value = self.total_open_position_value + self.total_closed_position_value
        self.total_adjustments = self.total_dividends_received + self.total_cash_settlements_received
        self.net_pl = self.total_position_value - self.total_position_cost
        self.net_realised_pl = self.total_closed_position_value - self.total_closed_position_cost
        self.net_unrealised_pl = self.total_open_position_value - self.total_open_position_cost

        try:
            self.net_pl_percentage = self.total_position_value / self.total_position_cost * 100 - 100
        except ZeroDivisionError:
            self.net_pl_percentage = 0.0

        try:
            self.net_realised_pl_percentage = \
                self.total_closed_position_value / self.total_closed_position_cost * 100 - 100
        except ZeroDivisionError:
            self.net_realised_pl_percentage = 0.0

        try:
            self.net_unrealised_pl_percentage = \
                self.total_open_position_value / self.total_open_position_cost * 100 - 100
        except ZeroDivisionError:
            self.net_unrealised_pl_percentage = 0.0

        self.revenue = self.total_adjustments + self.total_closed_position_value
        self.expenses = self.total_position_cost
        self.net_income = self.revenue - self.expenses

        self.net_contribution = self.total_deposits - self.total_withdrawals

        # TODO: Include dividends receivable once ex-dividend date data is available.
        self.accounts_receivable = self.total_open_position_value

        self.available_cash = self.net_contribution + self.net_income
        self.assets = self.accounts_receivable + self.available_cash

        self.equity = self.assets
        self.equity_change = (self.equity / self.total_deposits * 100) - 100
        self.equity_cagr = (self.equity / self.total_deposits) ** (1 / self.portfolio_age) - 1

    def __str__(self) -> str:
        result = ''

        # TODO: Use multiline string instead.
        result += '#' * 80 + '\n'
        result += 'Portfolio Summary\n'
        result += '#' * 80 + '\n'

        result += f'Net P&L: {self.format_net_value(self.net_pl)} {self.format_change(self.net_pl_percentage)}%\n'
        result += f'\tRealised P&L:   {self.format_net_value(self.net_realised_pl)} ' \
                  f'{self.format_change(self.net_realised_pl_percentage)}%\n'
        result += f'\t\tClosed Position(s) Value: {self.total_closed_position_value:.2f}\n'
        result += f'\t\tClosed Position(s) Cost: ({self.total_closed_position_cost:.2f})\n'
        result += f'\tUnrealised P&L: {self.format_net_value(self.net_unrealised_pl)} ' \
                  f'{self.format_change(self.net_unrealised_pl_percentage)}%\n'
        result += f'\t\tOpen Position(s) Value:   {self.total_open_position_value:.2f}\n'
        result += f'\t\tOpen Position(s) Cost:   ({self.total_open_position_cost:.2f})\n'
        result += '\n'

        result += f'Equity: {self.equity:.2f} {self.format_change(self.equity_change)}% ' \
                  f'(CAGR: {self.equity_cagr * 100:.2f}%)\n'
        result += f'\tAccounts Receivable: {self.format_net_value(self.accounts_receivable)}\n'
        result += f'\t\tEquities: {self.total_open_position_value:.2f}\n'
        result += f"\tAvailable Cash: {self.available_cash:.2f}\n"
        result += f"\t\tNet Contribution: {self.format_net_value(self.net_contribution)}\n"
        result += f'\t\t\tDeposits:     {self.total_deposits:.2f}\n'
        result += f'\t\t\tWithdrawals: ({self.total_withdrawals:.2f})\n'
        result += f'\t\tNet Income: {self.format_net_value(self.net_income)}\n'
        result += f'\t\t\tRevenue: {self.revenue:.2f}\n'
        result += f'\t\t\t\tEquities:     {self.total_closed_position_value:.2f}\n'
        result += f'\t\t\t\tAdjustments:  {self.total_adjustments:.2f}\n'
        result += f'\t\t\t\t\tDividends:         {self.total_dividends_received:.2f}\n'
        result += f'\t\t\t\t\tCash Settlements:  {self.total_cash_settlements_received:.2f}\n'
        result += f'\t\t\tExpenses: ({self.expenses:.2f})\n'
        result += f'\t\t\t\tEquities: ({self.total_position_cost:.2f})\n'
        result += f'\t\t\t\t\tOpen Positions:   ({self.total_open_position_cost:.2f})\n'
        result += f'\t\t\t\t\tClosed Positions: ({self.total_closed_position_cost:.2f})\n'
        result += '\n'

        return result

    @staticmethod
    def format_change(value: float) -> str:
        return f"{'+' if value > 0 else ''}{value:.2f}"

    @staticmethod
    def format_net_value(value: float) -> str:
        formatted_value = f"{abs(value):.2f}"

        if value < 0:
            formatted_value = f"({formatted_value})"
        else:
            formatted_value = f" {formatted_value} "

        return formatted_value
