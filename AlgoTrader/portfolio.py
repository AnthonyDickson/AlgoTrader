from typing import List, Set, Dict, Optional

from AlgoTrader.core import Position, Ticker


class InsufficientFundsError(Exception):
    """An exception indicated a lack of funds."""
    pass


class Portfolio:
    def __init__(self, initial_balance: float = 100000.00):
        self._balance: float = initial_balance
        self._initial_balance: float = initial_balance

        self._positions: List[Position] = []
        self._tickers: Set[Ticker] = set()

    @property
    def tickers(self) -> Set[Ticker]:
        """The set of tickers of the positions in this portfolio."""
        return self._tickers

    @property
    def initial_balance(self):
        """The available amount of cash that the portfolio started with."""
        return self._initial_balance

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
        self.total_position_cost = sum(position.cost for position in open_positions) + \
                                   sum(position.cost for position in closed_positions)
        self.total_open_position_value = \
            sum(position.quantity * stock_price for position in open_positions)
        self.total_open_position_cost = sum(position.cost for position in open_positions)

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


class PortfolioSummary:
    """Summary report of the performance of the portfolio."""

    def __init__(self, portfolio: Portfolio, stock_prices: Dict[Ticker, float]):
        """
        Create a summary report of a portfolio.
        :param portfolio: The portfolio to report on.
        :param stock_prices: The current prices of the securities present in the given portfolio.
        """

        self.ticker_position_summaries: Dict[Ticker, TickerPositionSummary] = {
            ticker: TickerPositionSummary(ticker, portfolio, stock_prices[ticker]) for ticker in portfolio.tickers
        }

        self.worst_performer_key = min(self.ticker_position_summaries,
                                       key=lambda ticker: self.ticker_position_summaries[ticker].net_pl)
        self.worst_performer = self.ticker_position_summaries[self.worst_performer_key]

        self.best_performer_key = max(self.ticker_position_summaries,
                                      key=lambda ticker: self.ticker_position_summaries[ticker].net_pl)
        self.best_performer = self.ticker_position_summaries[self.best_performer_key]

        self.total_open_position_value: float = 0.0
        self.net_realised_pl: float = 0.0
        self.net_unrealised_pl: float = 0.0

        for ticker in sorted(portfolio.tickers):
            ticker_position_summary = self.ticker_position_summaries[ticker]

            self.total_open_position_value += ticker_position_summary.total_open_position_value
            self.net_realised_pl += ticker_position_summary.realised_pl
            self.net_unrealised_pl += ticker_position_summary.unrealised_pl

        self.balance = portfolio.balance
        self.initial_balance = portfolio.initial_balance
        self.equity = self.balance + self.total_open_position_value
        self.net_change = self.balance - self.initial_balance
        self.net_change_percentage = self.balance / self.initial_balance * 100 - 100
        self.net_pl = self.equity - self.initial_balance
        self.net_pl_percentage = self.net_pl / self.initial_balance * 100
        self.net_realised_pl_percentage = self.net_realised_pl / self.initial_balance * 100
        self.net_unrealised_pl_percentage = self.net_unrealised_pl / self.initial_balance * 100

    def __str__(self) -> str:
        result = ''

        result += '#' * 80 + '\n'
        result += 'Portfolio Summary\n'
        result += '#' * 80 + '\n'

        result += '#' * 40 + '\n'
        result += 'Position Summary by Ticker\n'
        result += '#' * 40 + '\n'

        for ticker in sorted(self.ticker_position_summaries.keys()):
            result += f'{self.ticker_position_summaries[ticker]}\n'

        result += f'Worst Performer P&L: [{self.worst_performer_key}] {self.worst_performer.net_pl:.2f} ({self.worst_performer.net_pl_percentage:.2f}%)\n'
        result += f'Best Performer P&L:  [{self.best_performer_key}] {self.best_performer.net_pl:.2f} ({self.best_performer.net_pl_percentage:.2f}%)\n'

        result += '#' * 40 + '\n'
        result += 'Portfolio Valuation\n'
        result += '#' * 40 + '\n'

        result += f'Initial Balance: {self.initial_balance:.2f}\n'
        result += f'Balance: {self.balance:.2f}\n'
        result += f'Total Open Position Value: {self.total_open_position_value:.2f}\n'
        result += f'Equity: {self.equity:.2f}\n'
        result += f'Net P&L: {self.net_pl:.2f} ({self.net_pl_percentage:.2f}%)\n'
        result += f'Realised P&L: {self.net_realised_pl:.2f} ({self.net_realised_pl_percentage:.2f}%)\n'
        result += f'Unrealised P&L: {self.net_unrealised_pl:.2f} ({self.net_unrealised_pl_percentage:.2f}%)'

        return result
