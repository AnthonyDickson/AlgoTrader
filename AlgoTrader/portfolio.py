import sqlite3
from typing import List, Set, Dict, Optional

from AlgoTrader.exceptions import InsufficientFundsError
from AlgoTrader.position import Position
from AlgoTrader.types import PortfolioID, Ticker


# TODO: Sync state with database.
class Portfolio:

    def __init__(self, owner_name: str, db_connection: sqlite3.Connection):
        self._balance: float = 0.0
        self._contribution: float = 0.0

        self._positions: List[Position] = []
        self._tickers: Set[Ticker] = set()

        self._owner_name = owner_name

        self.db_cursor = db_connection.cursor()

        with self.db_cursor.connection:
            self.db_cursor.execute('''
                    INSERT INTO portfolio (owner_name) VALUES (?)
                    ''', (self._owner_name,))

        self._id = PortfolioID(self.db_cursor.lastrowid)

    def __del__(self):
        try:
            self.db_cursor.close()
        except sqlite3.ProgrammingError:
            pass

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
    def positions(self) -> List[Position]:
        """The list of positions (both open and closed) in this portfolio."""
        return self._positions[:]

    @property
    def open_positions(self) -> List[Position]:
        """The list of open positions in this portfolio."""
        return list(filter(lambda position: not position.is_closed, self._positions))

    @property
    def closed_positions(self) -> List[Position]:
        """The list of closed positions in this portfolio."""
        return list(filter(lambda position: position.is_closed, self._positions))

    def sync(self):
        """Sync the portfolio data with the database."""
        self.db_cursor.execute(
            '''SELECT balance FROM portfolio_balance WHERE portfolio_id = ?''',
            (self.id,)
        )

        new_balance = self.db_cursor.fetchone()['balance']

        # TODO: Fix database and local balances diverging due to different floating point precision...
        # assert abs(self._balance - new_balance) < sys.float_info.epsilon, \
        #     f"Balances do not match: expected {new_balance}, but got {self._balance}"

        self._balance = new_balance

    def open_position(self, ticker: Ticker, price: float, quantity: int) -> Position:
        """
        Open a position and add it to this portfolio.

        :param ticker: The ticker of the security that is being bought.
        :param price: The current price of the security.
        :param quantity: How many shares of the security that is being bought.
        :return: The opened position.
        :raises InsufficientFundsError: if there is not enough funds to open the given position.
        """
        # Deduct cost first to ensure that the account has enough funds (it will raise an exception if it doesn't).
        self._deduct(price * quantity)

        position = Position(self.id, ticker, price, quantity, self.db_cursor.connection)

        self._positions.append(position)
        self._tickers.add(position.ticker)

        return position

    def close_position(self, position: Position, price: float):
        """
        Close the given position at the given price.
        :param position: The position to close.
        :param price: The current price of the security the position covers.
        :raises AssertionError: if the position was not added to the portfolio.
        """
        assert position in self.positions, 'Cannot close a position that does not belong to this portfolio.'

        self._balance += position.close(price)

    def print_summary(self, stock_prices: Dict[Ticker, float], ticker: Optional[Ticker] = None):
        """
        Print a summary of the portfolio.
        :param stock_prices: The current prices of the stocks that this portfolio has positions in.
        :param ticker: (optional) If a ticker is specified, then a summary just for the positions for that ticker will
        be printed.
        """
        if ticker is not None:
            print(TickerPositionSummary(ticker, self, stock_prices[ticker]))
            return

        print(PortfolioSummary(self, stock_prices))

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


# TODO: Update to use data from database.
# TODO: Upload reports to database.
class TickerPositionSummary:
    """Summary report for all positions for a given ticker."""

    def __init__(self, ticker: Ticker, portfolio: Portfolio, stock_price: float):
        """
        Create a summary of positions for a given security.
        :param ticker: The ticker of the security to report on.
        :param portfolio: The portfolio that contains the positions.
        :param stock_price: The current stock price for the given security.
        """
        self.ticker = ticker
        self.total_num_closed_positions: float = 0.0
        self.total_num_open_positions: float = 0.0
        self.total_closed_position_cost: float = 0.0
        self.total_closed_position_value: float = 0.0
        self.realised_pl: float = 0.0
        self.total_num_closed_positions: float = 0.0
        self.total_open_position_cost: float = 0.0
        self.total_open_position_value: float = 0.0
        self.unrealised_pl: float = 0.0
        self.total_dividends_received: float = 0.0
        self.total_cash_settlements_received: float = 0.0

        for position in portfolio.positions:
            if position.is_closed:
                self.total_num_closed_positions += 1
                self.total_closed_position_cost += position.cost
                self.total_closed_position_value += position.exit_value
                self.realised_pl += position.realised_pl
            else:
                self.total_num_open_positions += 1
                self.total_open_position_cost += position.cost
                self.total_open_position_value += position.current_value(stock_price)
                self.unrealised_pl += position.unrealised_pl(stock_price)

            self.total_dividends_received += position.dividends_received
            self.total_cash_settlements_received += position.cash_settlements_received

        self.total_num_positions = self.total_num_open_positions + self.total_num_closed_positions
        self.total_position_cost = self.total_open_position_cost + self.total_closed_position_cost
        self.total_position_value = self.total_open_position_value + self.total_closed_position_value
        self.total_adjustments = self.total_dividends_received + self.total_cash_settlements_received
        self.net_pl = self.realised_pl + self.unrealised_pl

        try:
            self.net_pl_percentage = self.net_pl / self.total_position_cost * 100
        except ZeroDivisionError:
            self.net_pl_percentage = 0.0

    def __str__(self) -> str:
        ticker_prefix = f'[{self.ticker}]'

        return (
            f'{ticker_prefix:6s} P/L: {self.net_pl_percentage:.2f}% '
            f'({self.net_pl:.2f}) ({self.realised_pl:.2f} realised, {self.unrealised_pl:.2f} unrealised)'
            f' - Adjustments: {self.total_adjustments:.2f} '
            f'({self.total_dividends_received:.2f} from dividends, '
            f'{self.total_cash_settlements_received:.2f} from cash settlements)'
        )


# TODO: Update to use data from database.
# TODO: Calculate unrealised and net p&L using transaction data.
# TODO: Upload reports to database.
# TODO: Include YoY P&L - this can be done by reading transaction data.
class PortfolioSummary:
    """Summary report of the performance of the portfolio."""

    def __init__(self, portfolio: Portfolio, stock_prices: Dict[Ticker, float]):
        """
        Create a summary report of a portfolio.
        :param portfolio: The portfolio to report on.
        :param stock_prices: The current prices of the securities present in the given portfolio.
        """
        # TODO: Track withdrawals amount.
        self.total_withdrawals: float = 0.0
        self.total_num_closed_positions: float = 0.0
        self.total_num_open_positions: float = 0.0
        self.total_closed_position_cost: float = 0.0
        self.total_closed_position_value: float = 0.0
        self.realised_pl: float = 0.0
        self.total_num_closed_positions: float = 0.0
        self.total_open_position_cost: float = 0.0
        self.total_open_position_value: float = 0.0
        self.unrealised_pl: float = 0.0
        self.total_dividends_received: float = 0.0
        self.total_cash_settlements_received: float = 0.0

        for position in portfolio.positions:
            self.total_dividends_received += position.dividends_received
            self.total_cash_settlements_received += position.cash_settlements_received

            if position.is_closed:
                self.total_num_closed_positions += 1
                self.total_closed_position_cost += position.cost
                self.total_closed_position_value += position.exit_value
                self.realised_pl += position.realised_pl
            else:
                self.total_num_open_positions += 1
                self.total_open_position_cost += position.cost

                try:
                    stock_price = stock_prices[position.ticker]

                    self.total_open_position_value += position.current_value(stock_price)
                    self.unrealised_pl += position.unrealised_pl(stock_price)
                except KeyError:
                    print(f'WARNING: Missing stock prices for {position.ticker}.')

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

        self.balance = portfolio.balance
        self.contribution = portfolio.contribution
        self.net_contribution = self.contribution - self.total_withdrawals

        self.equity = self.balance + self.total_open_position_value
        self.equity_change = (self.equity / self.net_contribution * 100) - 100

        self.revenue = self.total_adjustments + self.total_closed_position_value
        self.income = self.contribution + self.revenue
        self.expenses = self.total_withdrawals + self.total_open_position_cost

    def __str__(self) -> str:
        result = ''

        result += '#' * 80 + '\n'
        result += 'Portfolio Summary\n'
        result += '#' * 80 + '\n'

        result += f'Equity: {self.equity:.2f} ({self.format_change(self.equity_change)}%)\n'
        result += f'\tTotal Open Position(s) Value: {self.total_open_position_value:.2f}\n'
        result += f'\tBalance: {self.balance:.2f}\n'

        result += f'\t\tIncome: {self.income:.2f}\n'
        result += f'\t\t\tTotal Deposits: {self.contribution:.2f}\n'
        result += f'\t\t\tRevenue: {self.revenue:.2f}\n'
        result += f'\t\t\t\tAdjustments: {self.total_adjustments:.2f}\n'
        result += f'\t\t\t\t\tDividends: {self.total_dividends_received:.2f}\n'
        result += f'\t\t\t\t\tCash Settlements: {self.total_cash_settlements_received:.2f}\n'
        result += f'\t\t\t\tClosed Positions: {self.total_closed_position_value:.2f}\n'

        result += f'\t\tExpenses: ({self.expenses:.2f})\n'
        result += f'\t\t\tWithdrawals: ({self.total_withdrawals:.2f})\n'
        result += f'\t\t\tOpen Positions: ({self.total_open_position_cost:.2f})\n'
        result += '\n'

        result += f'Net P&L: {self.format_change(self.net_pl)} ({self.format_change(self.net_pl_percentage)}%)\n'
        result += f'\tRealised P&L: {self.format_change(self.net_realised_pl)} ' \
            f'({self.format_change(self.net_realised_pl_percentage)}%)\n'
        result += f'\t\tClosed Position(s) Value: {self.total_closed_position_value:.2f}\n'
        result += f'\t\tClosed Position(s) Cost: ({self.total_closed_position_cost:.2f})\n'
        result += f'\tUnrealised P&L: {self.format_change(self.net_unrealised_pl)} ' \
            f'({self.format_change(self.net_unrealised_pl_percentage)}%)\n'
        result += f'\t\tOpen Position(s) Value: {self.total_open_position_value:.2f}\n'
        result += f'\t\tOpen Position(s) Cost: ({self.total_open_position_cost:.2f})\n'

        return result

    @staticmethod
    def format_change(value: float) -> str:
        return f"{'+' if value > 0 else ''}{value:.2f}"
