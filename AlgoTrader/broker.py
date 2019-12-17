import datetime
import enum
import sqlite3
from collections import defaultdict
from typing import Dict, List, DefaultDict, Optional

from AlgoTrader.portfolio import Portfolio
from AlgoTrader.position import Position
from AlgoTrader.types import PortfolioID, Ticker


# TODO: Grab these from the server.
class TransactionType(enum.Enum):
    DEPOSIT = enum.auto()
    WITHDRAWAL = enum.auto()
    BUY = enum.auto()
    SELL = enum.auto()
    DIVIDEND = enum.auto()
    CASH_SETTLEMENT = enum.auto()


# TODO: Adjust for stock splits.
class Broker:
    """A broker manages portfolios and executes buy/sell orders on behalf of traders."""

    def __init__(self, database_connection: sqlite3.Connection):
        """
        Create a new broker.

        :param database_connection: A connection to a database that can be queried for stock price data.
        """
        self.today = datetime.datetime.fromtimestamp(0.0)
        self.database_cursor = database_connection.cursor()
        # TODO: Read portfolios and positions from database?
        self.portfolios: Dict[PortfolioID, Portfolio] = dict()
        self.positions_by_portfolio: DefaultDict[PortfolioID, List[Position]] = defaultdict(lambda: [])
        self.positions_by_ticker: DefaultDict[Ticker, List[Position]] = defaultdict(lambda: [])

    def __del__(self):
        try:
            self.database_cursor.close()
        except sqlite3.ProgrammingError:
            pass

    def create_portfolio(self, owner_name: str, initial_contribution: float = 0.00) -> PortfolioID:
        """
        Create a new portfolio .

        :param owner_name: The name of the entity that the portfolio is being created for.
        :param initial_contribution: How much cash the portfolio should start with.
        :return: The ID of the created portfolio.
        """
        portfolio = Portfolio(owner_name, self.database_cursor.connection)
        self.portfolios[portfolio.id] = portfolio

        self._execute_transaction(portfolio.id, TransactionType.DEPOSIT, 1, initial_contribution, self.today)

        return portfolio.id

    def add_contribution(self, amount: float, portfolio_id: PortfolioID):
        """
        Add an amount of cash to the given portfolio as an contribution.

        :param amount: The amount of cash to add.
        :param portfolio_id: The portfolio to add the cash to.
        """
        self._execute_transaction(portfolio_id, TransactionType.DEPOSIT, 1, amount, self.today)

        self.portfolios[portfolio_id].add_contribution(amount)

    def get_balance(self, portfolio_id: PortfolioID) -> float:
        """
        Get the balance of a given user's portfolio.

        :param portfolio_id: The ID of the portfolio.
        :return: The available balance of the portfolio.
        """
        return self.portfolios[portfolio_id].balance

    def get_open_positions(self, portfolio_id: PortfolioID) -> List[Position]:
        """
        Get the open positions for the given portfolio.

        :param portfolio_id: The portfolio to check for open positions.
        :return: A list of open positions.
        """
        portfolio_id_in_database = self.portfolios[portfolio_id].id_in_database

        self.database_cursor.execute(
            '''SELECT position_id FROM open_positions WHERE portfolio_id = ?''',
            (portfolio_id_in_database,)
        )

        open_position_ids = {row['position_id'] for row in self.database_cursor}

        return list(filter(lambda position: position.id_in_database in open_position_ids,
                           self.portfolios[portfolio_id].positions))

    def execute_buy_order(self, ticker: Ticker, quantity: int, timestamp: datetime.datetime, portfolio_id: PortfolioID):
        """
        Execute a buy order at the market price.

        :param ticker: The ticker of the security to buy.
        :param quantity: How many shares to buy.
        :param timestamp: When the buy order was placed.
        :param portfolio_id: The portfolio to add the new position to.
        """
        self.database_cursor.execute('''
                SELECT close
                FROM daily_stock_data
                WHERE ticker=? and datetime=?
                ''', (ticker, timestamp,))

        market_price = self.database_cursor.fetchone()['close']

        position = Position(portfolio_id, ticker, market_price, quantity)
        position.register(self.database_cursor)

        self._execute_transaction(portfolio_id, TransactionType.BUY, quantity, market_price, self.today,
                                  position.id_in_database)

        portfolio = self.portfolios[portfolio_id]
        portfolio.open(position)

        self.positions_by_portfolio[portfolio_id].append(position)
        self.positions_by_ticker[ticker].append(position)

    def close_position(self, position: Position, timestamp: datetime.datetime):
        """
        Close a position.

        :param position: The position to close.
        :param timestamp: The date and time at which the position was requested to be closed.
        """
        self.database_cursor.execute('''
                        SELECT close
                        FROM daily_stock_data
                        WHERE ticker=? and datetime=?
                        ''', (position.ticker, timestamp,))

        market_price = self.database_cursor.fetchone()['close']

        self._execute_transaction(position.portfolio_id, TransactionType.SELL, position.quantity, market_price,
                                  self.today, position.id_in_database)
        portfolio = self.portfolios[position.portfolio_id]
        portfolio.close(position, market_price)

    def update(self, now: datetime.datetime):
        """
        Perform an update step for the broker.

        This includes adjusting positions for dividends and stock splits.

        :param now: The date and time that should be considered to be 'now'. This affects what data is used.
        data.
        """
        self.database_cursor.execute('''
        SELECT ticker, dividend_amount, split_coefficient, open 
        FROM daily_stock_data
        WHERE datetime=? AND (dividend_amount > 0 OR split_coefficient > 0);
        ''', (now,))

        self.today = now

        for row in self.database_cursor:
            if row['dividend_amount'] > 0:
                # TODO: Only pay dividend for shares that were owned on the ex-dividend date.
                for position in filter(lambda p: not p.is_closed, self.positions_by_ticker[row['ticker']]):
                    self._execute_transaction(position.portfolio_id, TransactionType.DIVIDEND, position.quantity,
                                              row['dividend_amount'], self.today, position.id_in_database)
                    total_dividend = position.adjust_for_dividend(row['dividend_amount'])
                    self.portfolios[position.portfolio_id].pay(total_dividend)
            elif row['split_coefficient'] > 0:
                for position in filter(lambda p: not p.is_closed, self.positions_by_ticker[row['ticker']]):
                    whole_shares, fractional_shares, cash_settlement_amount = \
                        position.adjust_for_stock_split(row['open'], row['split_coefficient'])

                    if cash_settlement_amount > 0:
                        self._execute_transaction(position.portfolio_id, TransactionType.CASH_SETTLEMENT, 1,
                                                  cash_settlement_amount, self.today, position.id_in_database)
                    if whole_shares == 0:
                        self._execute_transaction(position.portfolio_id, TransactionType.SELL, 0, row['open'],
                                                  self.today, position.id_in_database)
                    self.portfolios[position.portfolio_id].pay(cash_settlement_amount)

    def _execute_transaction(self, portfolio_id: PortfolioID, transaction_type: TransactionType, quantity: int,
                             value: float, timestamp: datetime.datetime, position_id: Optional[int] = None):
        portfolio_id_in_database = self.portfolios[portfolio_id].id_in_database

        self.database_cursor.execute(
            '''
            INSERT INTO transactions (portfolio_id, position_id, type, quantity, price, timestamp) 
                VALUES (?, ?, (SELECT transaction_type.id FROM transaction_type WHERE name=?), ?, ?, ?)
            ''',
            (portfolio_id_in_database, position_id, transaction_type.name, quantity, value, timestamp)
        )

        self.database_cursor.connection.commit()

    def print_report(self, portfolio_id: PortfolioID, date: datetime.datetime):
        """
        Print a summary report of the given portfolio.

        :param portfolio_id: The ID of the portfolio to report on.
        :param date: The date the report was requested for. This affects the stock prices used in the valuation.
        """
        portfolio = self.portfolios[portfolio_id]
        tickers = portfolio.tickers

        if len(tickers) == 0:
            portfolio.print_summary(dict())
        else:
            ticker_placeholders = ','.join(['?'] * len(tickers))

            self.database_cursor.execute(f'''
            SELECT ticker, close
            FROM daily_stock_data
            WHERE datetime=? AND ticker IN ({ticker_placeholders});
            ''', (date, *tuple(tickers)))

            stock_data = {row['ticker']: row['close'] for row in self.database_cursor.fetchall()}

            portfolio.print_summary(stock_data)
