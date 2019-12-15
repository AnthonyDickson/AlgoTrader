import datetime
import enum

from AlgoTrader.exceptions import InsufficientFundsError
from AlgoTrader.interfaces import ITradingBot
from AlgoTrader.portfolio import Portfolio
from AlgoTrader.position import Position
from AlgoTrader.utils import get_git_revision_hash


class TradingBotABC(ITradingBot):
    def __init__(self, initial_portfolio: Portfolio, git_hash: str = 'infer'):
        """
        Create a new bot.
        :param initial_portfolio: The portfolio that the bot starts with.
        :param git_hash: The
        """
        # Here to satisfy the linter.
        super().__init__(initial_portfolio, git_hash)

        self._portfolio = initial_portfolio

        self.git_hash = git_hash if git_hash != 'infer' else get_git_revision_hash()

    @property
    def portfolio(self) -> Portfolio:
        return self._portfolio

    def update(self, ticker, datum, prev_datum):
        """
        Perform an update step where the bot may or may not open or close positions.
        :param ticker: The ticker of the security to focus on.
        :param datum: The data for the given ticker for a given day. This should include both close prices and
        MACD information.
        :param prev_datum: The data for the given ticker for the previous day.
        """
        raise NotImplementedError


@enum.unique
class BuyPeriod(enum.Enum):
    DAILY = enum.auto()
    WEEKLY = enum.auto()
    MONTHLY = enum.auto()
    QUARTERLY = enum.auto()
    YEARLY = enum.auto()


class BuyAndHoldBot(TradingBotABC):
    """
    A bot that simply buys and holds shares periodically.
    """

    def __init__(self, initial_portfolio: Portfolio, git_hash: str = 'infer',
                 buy_period: BuyPeriod = BuyPeriod.MONTHLY):
        super().__init__(initial_portfolio, git_hash)

        assert buy_period in BuyPeriod, f'buy_period must be one of: {[period.name for period in BuyPeriod]}'

        self.buy_period = buy_period
        self.prev_purchase_date: datetime.datetime = datetime.datetime.fromtimestamp(0)

    def update(self, ticker, datum, prev_datum):
        """
        Perform an update step where the bot may or may not open or close positions.
        :param ticker: The ticker of the security to focus on.
        :param datum: The data for the given ticker for a given day.
        :param prev_datum: The data for the given ticker for the previous day.
        """
        today = datetime.datetime.fromisoformat(datum['datetime'])

        ticker_prefix = f'[{ticker}]'
        log_prefix = f'[{datum["datetime"]}] {ticker_prefix:6s}'

        should_buy: bool = self.buy_period == BuyPeriod.DAILY
        should_buy |= self.buy_period == BuyPeriod.WEEKLY and (today - self.prev_purchase_date).days > 7
        should_buy |= self.buy_period == BuyPeriod.MONTHLY and today.month > self.prev_purchase_date.month or \
                      (today.month == 1 and today.year > self.prev_purchase_date.year)
        should_buy |= (self.buy_period == BuyPeriod.QUARTERLY and
                       today.month % 3 == 1 and
                       (today.month > self.prev_purchase_date.month or today.year > self.prev_purchase_date.year))
        should_buy |= self.buy_period == BuyPeriod.YEARLY and today.year > self.prev_purchase_date.year

        if should_buy:
            market_price = datum['close']
            quantity = int((self.portfolio.balance * 0.01) / market_price)

            if quantity > 0:
                position = Position(ticker, market_price, quantity=quantity)

                try:
                    self.portfolio.open(position)
                    self.prev_purchase_date = today
                    print(f'{log_prefix} Opened new position: {quantity} share(s) @ {market_price}')
                except InsufficientFundsError:
                    pass


class MACDBot(TradingBotABC):
    """
    A trading (investing?) bot that buys and sells securities based on the
    MACD (Moving Average Convergence Divergence) indicator.
    """

    def update(self, ticker, datum, prev_datum):
        """
        Perform an update step where the bot may or may not open or close positions.
        :param ticker: The ticker of the security to focus on.
        :param datum: The data for the given ticker for a given day. This should include both close prices and
        MACD information.
        :param prev_datum: The data for the given ticker for the previous day.
        """
        ticker_prefix = f'[{ticker}]'
        log_prefix = f'[{datum["datetime"]}] {ticker_prefix:6s}'

        if prev_datum and datum['macd_histogram'] > 0 and datum['macd_line'] > datum['signal_line'] and \
                prev_datum['macd_line'] <= prev_datum['signal_line']:
            market_price = datum['close']

            if datum['macd_line'] < 0 and self.portfolio.balance >= market_price:
                quantity: int = (0.01 * self.portfolio.balance) // market_price

                if quantity > 0:
                    position = Position(ticker, market_price, quantity)
                    self.portfolio.open(position)

                    print(f'{log_prefix} Opened new position: {quantity} share(s) @ {market_price}')
        elif prev_datum and datum['macd_histogram'] < 0 and datum['macd_line'] < datum['signal_line'] and \
                prev_datum['macd_line'] >= prev_datum['signal_line']:
            if datum['macd_line'] > 0:
                market_price = datum['close']

                num_closed_positions: int = 0
                quantity_sold: int = 0
                net_pl: float = 0.0
                total_cost: float = 0.0
                total_exit_value: float = 0.0

                for position in self.portfolio.open_positions:
                    if position.ticker == ticker and position.entry_price < market_price:
                        self.portfolio.close(position, market_price)

                        net_pl += position.pl_realised
                        total_cost += position.cost
                        num_closed_positions += 1
                        quantity_sold += position.quantity
                        total_exit_value += position.exit_value

                if quantity_sold > 0:
                    avg_cost = total_cost / quantity_sold
                    percent_change = (total_exit_value / total_cost) * 100 - 100

                    print(
                        f'{log_prefix} Closed {num_closed_positions} position(s) @ {market_price} for a net profit of '
                        f'{net_pl:.2f} ({percent_change:.2f}%)(sold {quantity_sold} share(s) with an average cost of '
                        f'{avg_cost:.2f}/share).')
