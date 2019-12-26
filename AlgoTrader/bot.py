import datetime
import hashlib
import json
import re
import time
from typing import Optional, Set, Callable, Union, Iterable, Tuple, List, Dict

from AlgoTrader.broker import Broker
from AlgoTrader.exceptions import InsufficientFundsError
from AlgoTrader.types import PortfolioID, Ticker, Period, BuyQuantityFunc, ShouldSellFunc
from AlgoTrader.utils import Scheduler


class ContributionScheduler:
    """Handles periodic deposits into a brokerage account."""

    def __init__(self, amount: float, contribution_schedule: Scheduler):
        """
        Create a periodic contribution.

        :param amount: The cash amount to deposit each time.
        :param contribution_schedule: The schedule for contributions.
        """
        self.amount = float(amount)
        self.scheduler = contribution_schedule

        self.last_contribution_date = datetime.datetime.fromtimestamp(0.0)

    def get_contribution_amount(self, date: datetime.datetime) -> Optional[float]:
        if self.scheduler.has_period_elapsed(date, self.last_contribution_date):
            self.last_contribution_date = date

            return self.amount
        else:
            return None


class TickerList:
    """A wrapper for a list of tickers."""

    def __init__(self, tickers: Iterable[Ticker]):
        """
        Create a new ticker list.

        :param tickers: The list of tickers.
        """
        self.tickers = tickers

    def __iter__(self):
        """Get an iterator for this ticker list."""
        return iter(self.tickers)


class HistoricalTickerList(TickerList):
    """A list of tickers, indexed by date."""

    def __init__(self, historical_tickers: Dict[str, Iterable[Ticker]]):
        """
        Create a new historical ticker list.

        :param historical_tickers: A dictionary mapping dates to lists of tickers.
        """
        self.historical_tickers = historical_tickers
        self.date = min(self.historical_tickers)

        super().__init__(self.historical_tickers[self.date])

    def __getitem__(self, date: datetime.datetime) -> Iterable[Ticker]:
        """
        Get the ticker list for the given date.

        :param date: The date of the list to use.
        :return: The ticker list for the given date.
        :raise KeyError: if there is no list for the given date.
        """
        return self.historical_tickers[str(date)]

    def use_ticker_list(self, date: datetime.datetime):
        """
        Use the ticker list for the given date.

        Note: If there is not list for the given date, this method has no effect.

        :param date: The date of the list to use.
        """
        if str(date) in self.tickers:
            self.tickers = self[date]


class TickerListFactory:
    """A class for constructing and validating ticker lists from various sources."""

    # Any tickers such as 'BRK.A' that have a suffix included should have the period replaced with a hyphen.
    supported_formats = ['JSON']
    ticker_pattern = re.compile(r"^[A-Z]+(-[A-Z]+)?$")
    max_ticker_length = 6  # NYSE max ticker length is five characters, and NASDAQ is six.

    @staticmethod
    def load(ticker_list: Union[str, Set[Ticker], List[Ticker]]) -> 'TickerList':
        """
        Load a ticker list from various sources.

        :param ticker_list: One of: a path to a file that contains a ticker list, or a ticker list (or set).
        :return: The constructed TickerList object.
        """
        if isinstance(ticker_list, (set, list)):
            loader = TickerListFactory._load_iterable
        elif ticker_list.endswith('.json'):
            loader = TickerListFactory._load_json
        else:
            raise NotImplementedError(f"File format not supported. Supported formats are: "
                                      f"{','.join(TickerListFactory.supported_formats)}")

        ticker_list, is_historical_list = loader(ticker_list)

        if is_historical_list:
            return HistoricalTickerList(ticker_list['tickers'])
        else:
            return TickerList(ticker_list['tickers'])

    @staticmethod
    def _load_iterable(ticker_list: Union[list, set]) -> Tuple[dict, bool]:
        """
        Load a ticker list from an iterable (list or set).

        :param ticker_list: The list or set of tickers.
        :return: A 2-tuple containing the ticker list as a dictionary and whether or not the list is a historical list.
        :raise ValueError: if the ticker list is not valid.
        """
        if not TickerListFactory._is_valid_ticker_list(ticker_list):
            raise ValueError("Invalid ticker list.")

        return {'tickers': ticker_list}, False

    @staticmethod
    def _is_valid_ticker_list(ticker_list: Union[List[Ticker], Set[Ticker]]) -> bool:
        """
        Check if the given ticker list contains valid tickers.

        :param ticker_list: The list or set of tickers to validate.
        :return: True if the ticker list is not empty and only contains valid tickers.
        """
        if len(ticker_list) == 0:
            return False

        for ticker in ticker_list:
            if not TickerListFactory._is_valid_ticker(ticker):
                return False

        return True

    @staticmethod
    def _is_valid_ticker(ticker: str) -> bool:
        """
        Check if the given ticker is valid.

        :param ticker: The ticker to validate.
        :return: True if the ticker is of a valid length and format, otherwise False.
        """
        if len(ticker) > TickerListFactory.max_ticker_length:
            return False

        return re.fullmatch(TickerListFactory.ticker_pattern, ticker) is not None

    @staticmethod
    def _load_json(ticker_list_path: str) -> Tuple[dict, bool]:
        """
        Load a ticker list from the given file path.

        :param ticker_list_path: The path to the file containing the ticker list.
        :return: A 2-tuple containing the ticker list as a dictionary and whether or not the list is a historical list.
        :raise ValueError: if the ticker list is not valid.
        """
        with open(ticker_list_path, 'r') as file:
            ticker_list = json.load(file)

        if 'tickers' not in ticker_list:
            raise KeyError("The property 'tickers' was not found.")

        is_historical_list = TickerListFactory._is_historical_list(ticker_list)

        if not is_historical_list and not TickerListFactory._is_valid_ticker_list(ticker_list['tickers']):
            raise ValueError("Invalid ticker list.")
        elif is_historical_list:
            for date in ticker_list['tickers']:
                if not TickerListFactory._is_valid_ticker_list(ticker_list['tickers'][date]):
                    raise ValueError("Invalid ticker list.")

        return ticker_list, is_historical_list

    @staticmethod
    def _is_historical_list(ticker_list: dict) -> bool:
        """
        Check if the given ticker list is a historical ticker list.

        A historical ticker list is a collection of multiple lists of tickers where each list is mapped to by a date.

        :param ticker_list: The ticker list to validate.
        :return: True if the given ticker list is a historical ticker list, False otherwise.
        """
        if isinstance(ticker_list['tickers'], (list, set)):
            return False

        for date in ticker_list['tickers']:
            try:
                datetime.datetime.fromisoformat(date)

                return isinstance(ticker_list['tickers'][date], (list, set))
            except (TypeError, ValueError):
                return False


class TradingBot:
    def __init__(self, initial_deposit: float, tickers: TickerList, buy_quantity: BuyQuantityFunc,
                 contribution_scheduler: Optional[ContributionScheduler] = None, name: Optional[str] = None):
        """
        Create a new bot.

        :param initial_deposit: The amount of money the bot should start with in its brokerage account.
        :param tickers: The tickers that this bot should trade in.
        :param buy_quantity: A function that takes the account balance and share price and returns the quantity of
        shares to buy.
        :param contribution_scheduler: (optional) An object that schedules regular deposits into the brokerage account.
        :param name: (optional) The name of the bot.
        """

        self.tickers = tickers
        sha1_hash = hashlib.sha1(bytes(int(time.time())))
        self.name = name if name else self.__class__.__name__ + '_' + sha1_hash.hexdigest()
        self.portfolio_id: Optional[PortfolioID] = None
        self.initial_contribution = initial_deposit
        self.contribution_scheduler = contribution_scheduler
        self.buy_quantity: BuyQuantityFunc = buy_quantity

    @property
    def portfolio_id(self) -> Optional[PortfolioID]:
        """Get the bot's current portfolio's ID."""
        return self._portfolio_id

    @portfolio_id.setter
    def portfolio_id(self, value: PortfolioID):
        """
        Set the bot's current portfolio ID.
        This will affect which portfolio the bot will use for any future trades.
        """
        self._portfolio_id = PortfolioID(value)

    def get_contribution_amount(self, date: datetime.datetime) -> Optional[float]:
        """
        Check the amount to contribute for the given date.

        :param date: The current date.
        :return: The amount to contribute for the given date.
        """
        return self.contribution_scheduler.get_contribution_amount(date)

    def update(self, today: datetime.datetime, broker: Broker):
        """
        Perform an update step where the bot may or may not open or close positions.

        :param today: Today's date.
        :param broker: The broker that facilitates trades.
        """
        contribution_amount = self.get_contribution_amount(today)

        if contribution_amount:
            broker.add_contribution(contribution_amount, self.portfolio_id)

        if isinstance(self.tickers, HistoricalTickerList):
            self.tickers.use_ticker_list(today)

    @staticmethod
    def from_config(config: dict) -> 'TradingBot':
        """
        Create a trading bot from a configuration dictionary.

        :param config: A dictionary file containing the configuration details.
        :return: The constructed bot object.
        """
        name = str(config['name'])
        initial_deposit = float(config['initial_deposit'])
        ticker_list = TickerListFactory.load(config['ticker_list'])

        contribution_scheduler = ContributionScheduler(
            float(config['contribution']['amount']),
            Scheduler.from_string(config['contribution']['frequency'])
        )

        quantity = config['buy_quantity']

        if isinstance(quantity, int):
            def get_buy_quantity(balance: float, price: float) -> int:
                return min(quantity, int(balance // price))
        elif isinstance(quantity, float):
            def get_buy_quantity(balance: float, price: float) -> int:
                return int((quantity * balance) // price)
        else:
            raise TypeError(f"Buy quantity must be an integer or a float, got {type(quantity)}.")

        if config['bot'] == "BuyAndHoldBot":
            bot_class = BuyAndHoldBot
            buy_schedule = Scheduler.from_string(config['buy_frequency'])

            kwargs = dict(buy_schedule=buy_schedule)
        elif config['bot'] == "MACDBot":
            bot_class = MACDBot

            threshold = config['sell_threshold']

            if isinstance(threshold, int):
                def should_sell(market_value: float, purchase_value: float) -> bool:
                    return market_value - purchase_value >= threshold
            elif isinstance(threshold, float):
                def should_sell(market_value: float, purchase_value: float) -> bool:
                    return (market_value / purchase_value) - 1 > threshold
            else:
                raise TypeError(f"Sell threshold must be an integer or a float, got '{type(threshold)}'.")

            kwargs = dict(should_sell=should_sell)
        else:
            raise ValueError(f"The bot type '{config['bot']}' is not supported.")

        return bot_class(initial_deposit, ticker_list, get_buy_quantity, contribution_scheduler, name, **kwargs)


class BuyAndHoldBot(TradingBot):
    """
    A bot that simply buys and holds shares periodically.
    """

    def __init__(self, initial_deposit: float, tickers: TickerList, buy_quantity: BuyQuantityFunc,
                 contribution: Optional[ContributionScheduler] = None, name: Optional[str] = None,
                 buy_schedule: Optional[Scheduler] = Scheduler(Period.WEEKLY, 1)):
        """
        Create a new BuyAndHold bot.

        :param initial_deposit: The amount of money the bot should start with in its brokerage account.
        :param tickers: The tickers that this bot should trade in.
        :param buy_quantity: A function that takes the account balance and share price and returns the quantity of
        shares to buy.
        :param contribution: (optional) A object that schedules regular deposits into the brokerage account.
        :param name: (optional) The name of the bot.
        :param buy_schedule: (optional) The schedule for buying shares. (default: WEEKLY)
        """

        super().__init__(initial_deposit, tickers, buy_quantity, contribution, name)

        self.buy_schedule = buy_schedule
        self.prev_purchase_date: datetime.datetime = datetime.datetime.fromtimestamp(0)

    def update(self, today: datetime.datetime, broker: Broker):
        super(BuyAndHoldBot, self).update(today, broker)

        for ticker in self.tickers:
            ticker_prefix = f'[{ticker}]'
            log_prefix = f'[{today}] {ticker_prefix:6s}'

            if self.buy_schedule.has_period_elapsed(today, self.prev_purchase_date):
                market_price = broker.get_quote(ticker)[0]['close']
                balance = broker.get_balance(self.portfolio_id)
                quantity = self.buy_quantity(balance, market_price)

                if quantity > 0:
                    try:
                        broker.execute_buy_order(ticker, quantity, self.portfolio_id)
                        self.prev_purchase_date = today
                        print(f'{log_prefix} Opened new position: {quantity} share(s) @ {market_price:.2f}')
                    except InsufficientFundsError:
                        pass


class MACDBot(TradingBot):
    """
    A trading (investing?) bot that buys and sells securities based on the
    MACD (Moving Average Convergence Divergence) indicator.
    """
    default_should_sell_func: ShouldSellFunc = lambda market_value, purchase_value: market_value > purchase_value

    def __init__(self, initial_deposit: float, tickers: TickerList, buy_quantity: Callable[[float, float], int],
                 contribution: Optional[ContributionScheduler] = None, name: Optional[str] = None,
                 should_sell: ShouldSellFunc = default_should_sell_func):
        super().__init__(initial_deposit, tickers, buy_quantity, contribution, name)

        self.should_sell: ShouldSellFunc = should_sell

    def update(self, today: datetime.datetime, broker: Broker):
        super(MACDBot, self).update(today, broker)

        for ticker in self.tickers:
            try:
                data, prev_data = broker.get_quote(ticker)
            except KeyError:
                continue

            ticker_prefix = f'[{ticker}]'
            log_prefix = f'[{today}] {ticker_prefix:6s}'

            try:
                has_bullish_crossover = data['signal_line'] < data['macd_line'] < 0 and prev_data['macd_line'] <= \
                                        prev_data['signal_line']
                should_buy = data['macd_histogram'] > 0 and has_bullish_crossover

                has_bearish_crossover = 0 < data['macd_line'] < data['signal_line'] and prev_data['macd_line'] >= \
                                        prev_data['signal_line']
                should_sell = data['macd_histogram'] < 0 and has_bearish_crossover
            # TypeError raised when `prev_data` is None or any of ['macd_line', 'signal_line', 'histogram'] are None for
            # `data` or `prev_data`.
            except TypeError:
                continue

            if should_buy:
                market_price = data['close']
                balance = broker.get_balance(self.portfolio_id)
                quantity: int = self.buy_quantity(balance, market_price)

                if quantity > 0:
                    broker.execute_buy_order(ticker, quantity, self.portfolio_id)

                    print(f'{log_prefix} Opened new position: {quantity} share(s) @ {market_price:.2f}')
            elif should_sell:
                market_price = data['close']

                num_closed_positions: int = 0
                quantity_sold: int = 0
                net_pl: float = 0.0
                total_cost: float = 0.0
                total_exit_value: float = 0.0

                open_positions = [
                    position for position in broker.get_open_positions_by_ticker(self.portfolio_id, ticker)
                    if self.should_sell(position.current_value(market_price), position.entry_value)
                ]

                for position in open_positions:
                    broker.close_position(position)

                    net_pl += position.realised_pl
                    total_cost += position.cost
                    num_closed_positions += 1
                    quantity_sold += position.quantity
                    total_exit_value += position.exit_value

                if quantity_sold > 0:
                    avg_cost = total_cost / quantity_sold
                    percent_change = (total_exit_value / total_cost) * 100 - 100

                    print(
                        f'{log_prefix} Closed {num_closed_positions} position(s) @ {market_price:.2f} for a net profit '
                        f'of {net_pl:.2f} ({percent_change:.2f}%)(sold {quantity_sold} share(s) with an average cost of'
                        f' {avg_cost:.2f}/share).')
