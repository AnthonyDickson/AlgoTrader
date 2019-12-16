import hashlib
from typing import List, Set, Dict, Optional

from AlgoTrader.exceptions import InsufficientFundsError
from AlgoTrader.position import Position
from AlgoTrader.types import PortfolioID, Ticker


class Portfolio:
    _next_id = 0

    def __init__(self, owner_name: str, initial_contribution: float = 0.00):
        self._balance: float = initial_contribution
        self._contribution: float = initial_contribution

        self._positions: List[Position] = []
        self._tickers: Set[Ticker] = set()

        self._owner_name = owner_name
        self._id: PortfolioID = hashlib.sha1(bytes(Portfolio._next_id)).hexdigest()
        Portfolio._next_id += 1

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

    def open(self, position: Position):
        """
        Open a position and add it to this portfolio.
        :param position: The position to open.
        :raises InsufficientFundsError: if there is not enough funds to open the given position.
        """
        if position.cost > self.balance:
            raise InsufficientFundsError(f'Not enough funds to open the position worth {position.cost}.')

        self._balance -= position.cost
        self._positions.append(position)
        self._tickers.add(position.ticker)
        position.portfolio = self

    def close(self, position: Position, price: float):
        """
        Close the given position at the given price.
        :param position: The position to close.
        :param price: The current price of the security the position covers.
        :raises AssertionError: if the position was not added to the portfolio.
        """
        assert position in self.positions, 'ERROR: Tried to close a position that does not belong to this portfolio.'

        position.close(price)
        self._balance += position.exit_value

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

    def add_contribution(self, amount: float):
        """
        Add an amount of cash to the balance of this portfolio as an contribution
        (i.e. the owner adds money to their account themselves).

        :param amount: The amount to add to the portfolio.
        """
        self.pay(amount)
        self._contribution += amount

    def pay(self, amount: float):
        """
        Add an amount of cash to the balance of this portfolio.

        :param amount: The amount to add to the portfolio.
        """
        if amount < 0:
            raise ValueError(f'Cannot add negative amount {amount} to balance.')

        self._balance += amount


class TickerPositionSummary:
    """Summary report for all positions for a given ticker."""

    def __init__(self, ticker: Ticker, portfolio: Portfolio, stock_price: float):
        """
        Create a summary of positions for a given security.
        :param ticker: The ticker of the security to report on.
        :param portfolio: The portfolio that contains the positions.
        :param stock_price: The current stock price for the given security.
        """
        open_positions = list(
            filter(lambda position: not position.is_closed and position.ticker == ticker, portfolio.positions)
        )

        closed_positions = list(
            filter(lambda position: position.is_closed and position.ticker == ticker, portfolio.positions)
        )

        self.ticker = ticker

        self.total_num_open_positions = len(open_positions)
        self.total_num_closed_positions = len(closed_positions)
        self.total_num_positions = self.total_num_open_positions + self.total_num_closed_positions

        self.total_open_position_value = \
            sum(position.current_value(stock_price) for position in open_positions)
        self.total_closed_position_value = \
            sum(position.exit_value for position in closed_positions)
        self.total_position_value = self.total_open_position_value + self.total_closed_position_value

        self.total_open_position_cost = sum(position.cost for position in open_positions)
        self.total_closed_position_cost = sum(position.cost for position in closed_positions)
        self.total_position_cost = self.total_open_position_cost + self.total_closed_position_cost

        self.realised_pl = sum(position.pl_realised for position in closed_positions)
        self.unrealised_pl = sum(position.pl_unrealised(stock_price) for position in open_positions)
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
        )


# TODO: Include YoY P&L
class PortfolioSummary:
    """Summary report of the performance of the portfolio."""

    def __init__(self, portfolio: Portfolio, stock_prices: Dict[Ticker, float]):
        """
        Create a summary report of a portfolio.
        :param portfolio: The portfolio to report on.
        :param stock_prices: The current prices of the securities present in the given portfolio.
        """

        self.ticker_position_summaries: Dict[Ticker, TickerPositionSummary] = dict()

        for ticker in portfolio.tickers:
            try:
                self.ticker_position_summaries[ticker] = TickerPositionSummary(ticker, portfolio, stock_prices[ticker])
            except KeyError:
                print(f'WARNING: Missing stock prices for {ticker}.')

        if len(portfolio.positions) > 0:
            self.worst_performer_ticker = min(self.ticker_position_summaries,
                                              key=lambda ticker: self.ticker_position_summaries[
                                                  ticker].net_pl_percentage)
            self.worst_performer = self.ticker_position_summaries[self.worst_performer_ticker]

            self.best_performer_ticker = max(self.ticker_position_summaries,
                                             key=lambda ticker: self.ticker_position_summaries[
                                                 ticker].net_pl_percentage)
            self.best_performer = self.ticker_position_summaries[self.best_performer_ticker]

            self.least_frequently_traded_ticker = \
                min(self.ticker_position_summaries,
                    key=lambda ticker: self.ticker_position_summaries[ticker].total_num_positions)
            self.least_frequently_traded = self.ticker_position_summaries[self.least_frequently_traded_ticker]

            self.most_frequently_traded_ticker = \
                max(self.ticker_position_summaries,
                    key=lambda ticker: self.ticker_position_summaries[ticker].total_num_positions)
            self.most_frequently_traded = self.ticker_position_summaries[self.most_frequently_traded_ticker]
        else:
            self.worst_performer_ticker = None
            self.worst_performer = None
            self.best_performer_ticker = None
            self.best_performer = None
            self.least_frequently_traded_ticker = None
            self.least_frequently_traded = None
            self.most_frequently_traded_ticker = None
            self.most_frequently_traded = None

        self.total_open_position_value: float = 0.0
        self.total_closed_position_value: float = 0.0
        self.total_open_position_cost: float = 0.0
        self.total_closed_position_cost: float = 0.0

        for ticker in portfolio.tickers:
            try:
                ticker_position_summary = self.ticker_position_summaries[ticker]

                self.total_open_position_value += ticker_position_summary.total_open_position_value
                self.total_closed_position_value += ticker_position_summary.total_closed_position_value
                self.total_open_position_cost += ticker_position_summary.total_open_position_cost
                self.total_closed_position_cost += ticker_position_summary.total_closed_position_cost
            except KeyError:
                print(f'WARNING: Missing stock prices for {ticker}.')

        self.total_position_value = self.total_open_position_value + self.total_closed_position_value
        self.total_position_cost = self.total_open_position_cost + self.total_closed_position_cost

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
        self.equity = self.balance + self.total_open_position_value

    def __str__(self) -> str:
        result = ''

        result += '#' * 80 + '\n'
        result += 'Portfolio Summary\n'
        result += '#' * 80 + '\n'

        result += '#' * 40 + '\n'
        result += 'Portfolio Valuation\n'
        result += '#' * 40 + '\n'

        result += f'Equity: {self.equity:.2f}\n'
        result += f'Total Contribution: {self.contribution:.2f}\n'
        result += f'Balance: {self.balance:.2f}\n'
        result += f'Net P&L: {self.net_pl:.2f} ({self.net_pl_percentage:.2f}%)\n'
        result += f'Realised P&L: {self.net_realised_pl:.2f} ({self.net_realised_pl_percentage:.2f}%)\n'
        result += f'Unrealised P&L: {self.net_unrealised_pl:.2f} ({self.net_unrealised_pl_percentage:.2f}%)\n'
        result += '\n'

        result += (f'Total Open Position Value/Cost: {self.total_open_position_value:.2f} / '
                   f'{self.total_open_position_cost:.2f}\n')
        result += (f'Total Closed Position Value/Cost: {self.total_closed_position_value:.2f} / '
                   f'{self.total_closed_position_cost:.2f}\n')

        if self.worst_performer_ticker and self.best_performer_ticker and self.most_frequently_traded_ticker:
            result += (f'Worst Performer P&L: [{self.worst_performer_ticker}] {self.worst_performer.net_pl:.2f} '
                       f'({self.worst_performer.net_pl_percentage:.2f}%)\n')
            result += (f'Best Performer P&L:  [{self.best_performer_ticker}] {self.best_performer.net_pl:.2f} '
                       f'({self.best_performer.net_pl_percentage:.2f}%)\n')
            result += (f'Least Frequently Traded:  [{self.least_frequently_traded_ticker}] '
                       f'{self.least_frequently_traded.total_num_positions} positions '
                       f'({self.least_frequently_traded.total_num_open_positions} open, '
                       f'{self.least_frequently_traded.total_num_closed_positions} closed)\n')
            result += (f'Most Frequently Traded:  [{self.most_frequently_traded_ticker}] '
                       f'{self.most_frequently_traded.total_num_positions} positions '
                       f'({self.most_frequently_traded.total_num_open_positions} open, '
                       f'{self.most_frequently_traded.total_num_closed_positions} closed)\n')

        result += '#' * 40 + '\n'
        result += 'Position Summary by Ticker\n'
        result += '#' * 40 + '\n'

        for ticker in sorted(self.ticker_position_summaries.keys()):
            result += f'{self.ticker_position_summaries[ticker]}\n'

        return result
