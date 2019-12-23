import datetime
import sqlite3
from typing import Set, Optional, Dict, Tuple

from AlgoTrader.exceptions import InsufficientFundsError
from AlgoTrader.formatting import format_net_value
from AlgoTrader.position import Position
from AlgoTrader.types import PortfolioID, Ticker, TransactionType, PositionID


# TODO: Sync state with database.
class Portfolio:

    def __init__(self, owner_name: str, timestamp: datetime.datetime,
                 db_connection: sqlite3.Connection):
        self._balance: float = 0.0
        self._contribution: float = 0.0
        self._taxes_paid: float = 0.0
        self._created_timestamp: datetime.datetime = timestamp
        self.positions: Set[Position] = set()
        self.open_positions: Set[Position] = set()
        self.closed_positions: Set[Position] = set()
        self.positions_by_id: Dict[PositionID, Position] = dict()
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
    def taxes_paid(self) -> float:
        """How much taxes this portfolio has paid to date."""
        return self._taxes_paid

    @property
    def balance(self) -> float:
        """The available amount of cash."""
        return self._balance

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
                      timestamp: datetime.datetime, position_id: Optional[PositionID] = None) -> Position:
        """
        Open a position and add it to this portfolio.

        :param ticker: The ticker of the security that is being bought.
        :param price: The current price of the security.
        :param quantity: How many shares of the security that is being bought.
        :param timestamp: When the position is being opened.
        :param position_id: (optional) If specified, creates the position using this ID (rather than inferring it).
        :return: The opened position.
        :raises InsufficientFundsError: if there is not enough funds to open the given position.
        """
        # Deduct cost first to ensure that the account has enough funds (it will raise an exception if it doesn't).
        self._deduct(price * quantity)

        position = Position(
            self.id,
            ticker,
            price,
            quantity,
            timestamp,
            self.db_connection if position_id is None else None,
            position_id
        )

        self._tickers.add(position.ticker)
        self.positions.add(position)
        self.open_positions.add(position)
        self.positions_by_id[position.id] = position

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
        self.open_positions.discard(position)
        self.closed_positions.add(position)

    def create_summary(self, period_end: datetime.datetime,
                       period_start: Optional[datetime.datetime] = None) -> 'PortfolioSummary':
        """
        Create a summary of the portfolio.

        :param period_end: The last date that is included in the reporting period.
        :param period_start: (optional) The first date that is included in the reporting period. If not specified, then
        the created_timestamp for when the portfolio was created will be used.
        """
        return PortfolioSummary(self, self.db_connection, period_end, period_start)

    def generate_tax_report(self, report_date: datetime.datetime) -> 'TaxReport':
        """
        Generate a tax report for the given tax year.

        :param report_date: The date that the report is being created on. This date's year minus one will be used for
        the tax year.
        :return: A completed tax report for this portfolio.
        """
        tax_year = datetime.datetime(year=report_date.year - 1, month=1, day=1, hour=0, minute=0, second=0,
                                     microsecond=0)

        return TaxReport(tax_year, self, self.db_connection)

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

    # TODO: Use self._deduct() to deduct maximum amount, any left over amount should be automatically deducted from
    #  future income.
    def deduct_taxes(self, amount: float):
        """
        Pay the taxman.

        Note: This may put the account into debt.

        :param amount: The amount of taxes to deduct from the account.
        """
        self._balance -= amount
        self._taxes_paid += amount

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

    def pay_for_buy_order(self, amount: float):
        """
        Pay for a (unfilled) buy order in advance.

        Note:
        - This is mainly used for batch orders where the creation of positions for buy orders are deferred.
        - If a buy order is going to filled straight away (i.e not issuing batch orders) then you should NOT call this
        method or the portfolio will be double charged.

        :param amount: The total price/cost of the buy order.
        """
        self._deduct(amount)

    def refund_unfilled_buy_order(self, amount: float):
        """
        Refund the amount of cash paid upfront for a buy order that was not filled straight away.

        Note:
        - This is mainly used for batch orders where the creation of positions for buy orders are deferred.

        :param amount: The amount to refund to the account.
        """
        self._pay(amount)

    def _pay(self, amount: float):
        """
        Add an amount of cash to the balance of this portfolio.

        :param amount: The amount to add to the portfolio.
        """
        if amount < 0:
            raise ValueError(f'Cannot add negative amount {amount} to balance.')
        elif amount > 0:
            self._balance += amount

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
# TODO: Include YoY P&L - this can be done by reading transaction data.
# TODO: Allow for summaries to be loaded from database.
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
            cursor = db_connection.execute(
                f'''
                SELECT ticker, close, MAX(datetime)
                FROM daily_stock_data
                WHERE datetime <= ?
                GROUP BY ticker;
                ''',
                (period_end,)
            )

            period_start = portfolio.created_timestamp
        else:
            cursor = db_connection.execute(
                f'''
                        SELECT ticker, close, MAX(datetime)
                        FROM daily_stock_data
                        WHERE ? <= datetime AND datetime <= ?
                        GROUP BY ticker;
                        ''',
                (period_start, period_end,)
            )

        stock_prices = {row['ticker']: row for row in cursor}
        cursor.close()

        self.total_deposits: float = 0.0
        self.total_withdrawals: float = 0.0
        self.total_dividends_received: float = 0.0
        self.total_cash_settlements_received: float = 0.0
        self.total_taxes_paid: float = 0.0

        cursor = db_connection.execute(
            f"""
            SELECT type, SUM(price * quantity) AS total
            FROM transactions 
            WHERE portfolio_id = ? AND ? <= timestamp AND timestamp <= ? AND type IN (?, ?, ?, ?, ?)
            GROUP BY type;
            """,
            (portfolio.id, period_start, period_end,
             TransactionType.DEPOSIT.value, TransactionType.WITHDRAWAL.value,
             TransactionType.DIVIDEND.value, TransactionType.CASH_SETTLEMENT.value, TransactionType.TAX.value)
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
            elif row['type'] == TransactionType.TAX.value:
                self.total_taxes_paid = row['total']
            else:
                raise ValueError(f"Got unexpected type from totals query: {row['type']}.")

        cursor.close()

        self.db_connection = db_connection

        self.date_created = portfolio.created_timestamp
        self.portfolio_id = portfolio.id
        self.period_start = period_start
        self.period_end = period_end
        self.portfolio_age: float = (self.period_end - self.date_created).days / 365.25

        self.total_num_closed_positions: float = 0.0
        self.total_num_open_positions: float = 0.0
        self.total_closed_position_cost: float = 0.0
        self.total_closed_position_value: float = 0.0
        self.total_num_closed_positions: float = 0.0
        self.total_open_position_cost: float = 0.0
        self.total_open_position_value: float = 0.0

        for position in portfolio.positions:
            if not position.is_closed and position.opened_timestamp >= self.period_start:
                self.total_num_open_positions += 1
                self.total_open_position_cost += position.cost

                try:
                    stock_price = stock_prices[position.ticker]['close']

                    self.total_open_position_value += position.current_value(stock_price)
                except KeyError:
                    print(f'WARNING: Missing stock prices for {position.ticker}.')
            elif position.is_closed and position.closed_timestamp <= self.period_end:
                self.total_num_closed_positions += 1
                self.total_closed_position_cost += position.cost
                self.total_closed_position_value += position.exit_value

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
        self.expenses = self.total_position_cost + self.total_taxes_paid
        self.net_income = self.revenue - self.expenses

        self.net_contribution = self.total_deposits - self.total_withdrawals

        # TODO: Include dividends receivable once ex-dividend date data is available.
        self.accounts_receivable = self.total_open_position_value

        self.available_cash = self.net_contribution + self.net_income
        self.assets = self.accounts_receivable + self.available_cash

        self.equity = self.assets
        self.equity_change = (self.equity / self.total_deposits * 100) - 100
        self.equity_cagr = (self.equity / self.total_deposits) ** (1 / self.portfolio_age) - 1

    def upload(self):
        """Upload the report to the database."""
        with self.db_connection:
            self.db_connection.execute(
                """
                INSERT INTO portfolio_report (
                    report_date, 
                    portfolio_id,
                    net_pl, 
                    net_pl_percentage, 
                    realised_pl, 
                    realised_pl_percentage, 
                    closed_position_value, 
                    closed_position_cost, 
                    unrealised_pl, 
                    unrealised_pl_percentage, 
                    open_position_value, 
                    open_position_cost, 
                    equity, 
                    equity_change, 
                    cagr, 
                    accounts_receivable, 
                    accounts_receivable_equities, 
                    available_cash, 
                    net_contribution, 
                    deposits, 
                    withdrawals, 
                    net_income, 
                    revenue, 
                    revenue_equities, 
                    adjustments,
                    dividends, 
                    cash_settlements, 
                    expenses, 
                    taxes, 
                    expenses_equities
                ) VALUES (
                    ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                    ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
                )
                """,
                (self.period_end,
                 self.portfolio_id,
                 self.net_pl,
                 self.net_pl_percentage,
                 self.net_realised_pl,
                 self.net_realised_pl_percentage,
                 self.total_closed_position_value,
                 self.total_closed_position_cost,
                 self.net_unrealised_pl,
                 self.net_unrealised_pl_percentage,
                 self.total_open_position_value,
                 self.total_open_position_cost,
                 self.equity,
                 self.equity_change,
                 self.equity_cagr,
                 self.accounts_receivable,
                 self.total_open_position_value,
                 self.available_cash,
                 self.net_contribution,
                 self.total_deposits,
                 self.total_withdrawals,
                 self.net_income,
                 self.revenue,
                 self.total_closed_position_value,
                 self.total_adjustments,
                 self.total_dividends_received,
                 self.total_cash_settlements_received,
                 self.expenses,
                 self.total_taxes_paid,
                 self.total_position_cost
                 )
            )

    def __str__(self) -> str:
        result = ''

        # TODO: Use multiline string instead.
        result += '#' * 80 + '\n'
        result += 'Portfolio Summary\n'
        result += '#' * 80 + '\n'

        result += f'Net P&L: {format_net_value(self.net_pl)} {self.format_change(self.net_pl_percentage)}%\n'
        result += f'\tRealised P&L:   {format_net_value(self.net_realised_pl)} ' \
                  f'{self.format_change(self.net_realised_pl_percentage)}%\n'
        result += f'\t\tClosed Position(s) Value: {self.total_closed_position_value:.2f}\n'
        result += f'\t\tClosed Position(s) Cost: ({self.total_closed_position_cost:.2f})\n'
        result += f'\tUnrealised P&L: {format_net_value(self.net_unrealised_pl)} ' \
                  f'{self.format_change(self.net_unrealised_pl_percentage)}%\n'
        result += f'\t\tOpen Position(s) Value:   {self.total_open_position_value:.2f}\n'
        result += f'\t\tOpen Position(s) Cost:   ({self.total_open_position_cost:.2f})\n'
        result += '\n'

        result += f'Equity: {self.equity:.2f} {self.format_change(self.equity_change)}% ' \
                  f'(CAGR: {self.equity_cagr * 100:.2f}%)\n'
        result += f'\tAccounts Receivable: {format_net_value(self.accounts_receivable)}\n'
        result += f'\t\tEquities: {self.total_open_position_value:.2f}\n'
        result += f"\tAvailable Cash: {self.available_cash:.2f}\n"
        result += f"\t\tNet Contribution: {format_net_value(self.net_contribution)}\n"
        result += f'\t\t\tDeposits:     {self.total_deposits:.2f}\n'
        result += f'\t\t\tWithdrawals: ({self.total_withdrawals:.2f})\n'
        result += f'\t\tNet Income: {format_net_value(self.net_income)}\n'
        result += f'\t\t\tRevenue:   {self.revenue:.2f}\n'
        result += f'\t\t\t\tEquities:     {self.total_closed_position_value:.2f}\n'
        result += f'\t\t\t\tAdjustments:  {self.total_adjustments:.2f}\n'
        result += f'\t\t\t\t\tDividends:         {self.total_dividends_received:.2f}\n'
        result += f'\t\t\t\t\tCash Settlements:  {self.total_cash_settlements_received:.2f}\n'
        result += f'\t\t\tExpenses: ({self.expenses:.2f})\n'
        result += f'\t\t\t\tTaxes:    ({self.total_taxes_paid:.2f})\n'
        result += f'\t\t\t\tEquities: ({self.total_position_cost:.2f})\n'
        result += f'\t\t\t\t\tOpen Positions:   ({self.total_open_position_cost:.2f})\n'
        result += f'\t\t\t\t\tClosed Positions: ({self.total_closed_position_cost:.2f})\n'
        result += '\n'

        return result

    @staticmethod
    def format_change(value: float) -> str:
        return f"{'+' if value > 0 else ''}{value:.2f}"


# TODO: Report on make-up of taxes (e.g. capital gains from equities vs. dividends).
class TaxReport:
    """Calculates and summarises the tax for a given portfolio."""

    # Dividend tax config
    holding_period_offset = 60
    holding_period_length = 121
    min_holding_period = 60

    def __init__(self, tax_year: datetime.datetime, portfolio: Portfolio, db_connection: sqlite3.Connection):
        """
        Create a tax report for a given year.

        :param tax_year: The tax year to calculate taxes for.
        :param portfolio: The portfolio to calculate taxes for.
        :param db_connection: A database connection that can be used for querying tax rates.
        """
        self.start_of_tax_year = datetime.datetime(year=tax_year.year, month=1, day=1)
        # TODO: Account for milliseconds? Not necessary?
        self.end_of_tax_year = datetime.datetime(year=tax_year.year, month=12, day=31,
                                                 hour=23, minute=59, second=59)
        self.report_date = datetime.datetime(tax_year.year + 1, 4, 15)

        self.portfolio_id = portfolio.id

        cursor = db_connection.cursor()
        cursor.execute(
            """
            SELECT 
                bracket_threshold AS threshold, 
                tax_rate AS rate 
            FROM historical_marginal_tax_rates 
            WHERE tax_year = ?
            """,
            (self.start_of_tax_year,)
        )

        ordinary_tax_rates = {row['threshold']: row['rate'] for row in cursor}

        cursor.execute(
            """
            SELECT 
                bracket_threshold AS threshold, 
                tax_rate AS rate 
            FROM historical_capital_gains_tax_rates 
            WHERE tax_year = ?
            """,
            (self.start_of_tax_year,)
        )

        capital_gains_tax_rates = {row['threshold']: row['rate'] for row in cursor}

        cursor.execute(
            """
            SELECT position_id, timestamp, (quantity * price) AS amount
            FROM transactions
            WHERE portfolio_id = ? 
                AND type = ? 
                AND ? <= timestamp AND timestamp <= ?
            """,
            (portfolio.id, TransactionType.DIVIDEND.value, self.start_of_tax_year, self.end_of_tax_year)
        )

        dividends_for_tax_year = cursor.fetchall()

        cursor.close()

        self.short_term_capital_gains: float = 0.0
        self.long_term_capital_gains: float = 0.0

        positions_closed_during_tax_year = filter(
            lambda p: self.start_of_tax_year <= p.closed_timestamp <= self.end_of_tax_year,
            portfolio.closed_positions
        )

        # Capital gains from sale of equities.
        for position in positions_closed_during_tax_year:
            if (position.closed_timestamp - position.opened_timestamp).days <= 365:
                self.short_term_capital_gains += position.realised_pl
            else:
                self.long_term_capital_gains += position.realised_pl

        # Capital gains from dividends.
        for row in dividends_for_tax_year:
            position = portfolio.positions_by_id[row['position_id']]
            dividend_date = datetime.datetime.fromisoformat(row['timestamp'])

            dividend_holding_period_end = dividend_date - datetime.timedelta(self.holding_period_offset)

            if position.opened_timestamp <= dividend_holding_period_end - datetime.timedelta(
                    self.min_holding_period) and \
                    (not position.is_closed or (
                            position.closed_timestamp - position.opened_timestamp).days > self.min_holding_period):
                # It is qualified dividend
                self.long_term_capital_gains += row['amount']
            else:
                self.short_term_capital_gains += row['amount']

        (self.short_term_capital_gains_tax,
         self.short_term_gains_tax_by_bracket,
         self.taxable_short_term_gains_amounts_by_bracket) = \
            self._calculate_tax(self.short_term_capital_gains, ordinary_tax_rates)

        (self.long_term_capital_gains_tax,
         self.long_term_gains_tax_by_bracket,
         self.taxable_long_term_gains_amounts_by_bracket) = \
            self._calculate_tax(self.long_term_capital_gains, capital_gains_tax_rates)

        self.deductible_losses = min(3000.00, abs(min(0.00, self.net_gains)))

    @property
    def net_gains(self) -> float:
        """The total amount of capital gains earned in the tax year."""
        return self.short_term_capital_gains + self.long_term_capital_gains

    @property
    def total_tax(self) -> float:
        """The total amount of tax payable for the tax year."""
        return self.short_term_capital_gains_tax + self.long_term_capital_gains_tax - self.deductible_losses

    def __str__(self):
        return f"""
{self.report_date.date()} Tax Report
Tax year: {self.start_of_tax_year.date()} - {self.end_of_tax_year.date()} 
Portfolio ID: {self.portfolio_id} 

Net Income: {format_net_value(self.net_gains)}
\tShort-Term Capital Gains: {format_net_value(self.short_term_capital_gains)}
\tLong-Term Capital Gains:  {format_net_value(self.long_term_capital_gains)}

Total Tax Payable: {self.total_tax:.2f}
\tShort-Term Capital Gains:  {self.short_term_capital_gains_tax:.2f}
\tLong-Term Capital Gains:   {self.long_term_capital_gains_tax:.2f}
\tDeductibles:              ({self.deductible_losses:.2f})
        """

    @staticmethod
    def _calculate_tax(net_income: float, tax_brackets: Dict[float, float]) \
            -> Tuple[float, Dict[float, float], Dict[float, float]]:
        """
        Calculate the tax due for the given net income and marginal tax rates.

        :param net_income: The net income for the tax year period.
        :param tax_brackets: A dictionary mapping the threshold to each bracket to the corresponding tax rate.
        :return: A 3-tuple containing, in this order: the total amount of tax, the amount of tax by tax bracket and the
        amount of taxable income by tax bracket.
        """
        residual_amount: float = net_income

        total_tax: float = 0.0
        payable_tax_by_rate: Dict[float, float] = dict()
        taxable_amounts_by_rate: Dict[float, float] = dict()

        for threshold in sorted(tax_brackets.keys(), reverse=True):
            rate = tax_brackets[threshold]

            if residual_amount >= threshold:
                taxable_amount = residual_amount - threshold
                amount_to_pay = rate * taxable_amount
                residual_amount -= taxable_amount

                taxable_amounts_by_rate[rate] = taxable_amount
                payable_tax_by_rate[rate] = amount_to_pay
                total_tax += amount_to_pay
            else:
                taxable_amounts_by_rate[rate] = 0.0
                payable_tax_by_rate[rate] = 0.0

        return total_tax, payable_tax_by_rate, taxable_amounts_by_rate
