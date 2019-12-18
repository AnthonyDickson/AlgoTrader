import abc
import datetime
import enum
import hashlib
import time
from typing import Optional, Iterable, Set, Dict

from AlgoTrader.broker import Broker
from AlgoTrader.exceptions import InsufficientFundsError
from AlgoTrader.interfaces import ITradingBot
from AlgoTrader.types import PortfolioID, Ticker


class TradingBotABC(ITradingBot, abc.ABC):
    def __init__(self, broker: Broker, tickers: Iterable[Ticker]):
        # Here to satisfy the linter.
        super().__init__(broker, tickers)

        self._broker = broker
        self._tickers = set(tickers)
        sha1_hash = hashlib.sha1(bytes(int(time.time())))
        self._name = self.__class__.__name__ + '_' + sha1_hash.hexdigest()
        self._portfolio_id: Optional[PortfolioID] = None

    @property
    def name(self) -> str:
        return self._name

    @property
    def tickers(self) -> Set[Ticker]:
        return self._tickers

    @property
    def portfolio_id(self) -> Optional[PortfolioID]:
        return self._portfolio_id

    @portfolio_id.setter
    def portfolio_id(self, value: PortfolioID):
        self._portfolio_id = PortfolioID(value)


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

    def __init__(self, broker: Broker, tickers: Iterable[Ticker], buy_period: BuyPeriod):
        """
        Create a new BuyAndHold bot.

        :param broker: The broker that will facilitate trades.
        :param tickers: The tickers that this bot will trade in.
        :param buy_period: How often the bot will buy positions.
        """
        super().__init__(broker, tickers)

        assert buy_period in BuyPeriod, f'buy_period must be one of: {[period.name for period in BuyPeriod]}'

        self.buy_period = buy_period
        self.prev_purchase_date: datetime.datetime = datetime.datetime.fromtimestamp(0)

    def update(self, today: datetime.datetime):
        for ticker in self.tickers:
            ticker_prefix = f'[{ticker}]'
            log_prefix = f'[{today}] {ticker_prefix:6s}'

            should_buy: bool = self.buy_period == BuyPeriod.DAILY
            should_buy |= self.buy_period == BuyPeriod.WEEKLY and (today - self.prev_purchase_date).days > 7
            should_buy |= self.buy_period == BuyPeriod.MONTHLY and today.month > self.prev_purchase_date.month or \
                          (today.month == 1 and today.year > self.prev_purchase_date.year)
            should_buy |= (self.buy_period == BuyPeriod.QUARTERLY and
                           today.month % 3 == 1 and
                           (today.month > self.prev_purchase_date.month or today.year > self.prev_purchase_date.year))
            should_buy |= self.buy_period == BuyPeriod.YEARLY and today.year > self.prev_purchase_date.year

            if should_buy:
                market_price = self._broker.get_quote(ticker)[0]['close']
                balance = self._broker.get_balance(self.portfolio_id)
                quantity = int((balance * 0.01) / market_price)

                if quantity > 0:
                    try:
                        self._broker.execute_buy_order(ticker, quantity, self.portfolio_id)
                        self.prev_purchase_date = today
                        print(f'{log_prefix} Opened new position: {quantity} share(s) @ {market_price}')
                    except InsufficientFundsError:
                        pass


class MACDBot(TradingBotABC):
    """
    A trading (investing?) bot that buys and sells securities based on the
    MACD (Moving Average Convergence Divergence) indicator.
    """

    def __init__(self, broker: Broker, historical_tickers: Dict[str, Dict[str, Set[Ticker]]]):
        super().__init__(broker, historical_tickers['tickers'][min(historical_tickers['tickers'].keys())])

        self.historical_tickers = historical_tickers['tickers']

    def update(self, today: datetime.datetime):
        if str(today) in self.historical_tickers:
            self._tickers.update(self.historical_tickers[str(today)])

        for ticker in self.tickers:
            try:
                data, prev_data = self._broker.get_quote(ticker)
            except KeyError:
                continue

            ticker_prefix = f'[{ticker}]'
            log_prefix = f'[{today}] {ticker_prefix:6s}'

            if prev_data and data['macd_histogram'] > 0 and 0 > data['macd_line'] > data['signal_line'] and \
                    prev_data['macd_line'] <= prev_data['signal_line']:
                market_price = data['close']
                balance = self._broker.get_balance(self.portfolio_id)
                quantity: int = int((0.01 * balance) // market_price)

                if quantity > 0:
                    self._broker.execute_buy_order(ticker, quantity, self.portfolio_id)

                    print(f'{log_prefix} Opened new position: {quantity} share(s) @ {market_price}')
            elif prev_data and data['macd_histogram'] < 0 and 0 < data['macd_line'] < data['signal_line'] and \
                    prev_data['macd_line'] >= prev_data['signal_line']:
                market_price = data['close']

                num_closed_positions: int = 0
                quantity_sold: int = 0
                net_pl: float = 0.0
                total_cost: float = 0.0
                total_exit_value: float = 0.0

                for position in self._broker.get_open_positions(self.portfolio_id):
                    if position.ticker == ticker and position.current_value(market_price) > position.entry_value:
                        self._broker.close_position(position)

                        net_pl += position.realised_pl
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
