from collections import defaultdict
import json
from statistics import mean
from typing import List, Dict, DefaultDict

import matplotlib.pyplot as plt
import pandas as pd

import plac


class MACDBot:
    pass


Ticker = str


class Position:
    def __init__(self, ticker: Ticker, entry_price: float, quantity: int = 1):
        self._ticker: Ticker = ticker
        self._entry_price: float = entry_price
        self._exit_price: float = 0.0
        self._quantity: int = quantity
        self._pl_realised: float = 0.0
        self._pl_unrealised: float = 0.0
        self._is_closed: bool = False

    @property
    def cost(self) -> float:
        return self._quantity * self._entry_price

    entry_value = cost

    @property
    def exit_value(self) -> float:
        return self.quantity * self._exit_price

    @property
    def entry_price(self) -> float:
        return self._entry_price

    @property
    def pl_realised(self) -> float:
        return self._pl_realised

    @property
    def quantity(self):
        return self._quantity

    def pl_unrealised(self, price) -> float:
        if self._is_closed:
            return 0.0
        else:
            self._pl_unrealised = self._quantity * (price - self._entry_price)

            return self._pl_unrealised

    def close(self, price: float):
        assert self._is_closed is not True, "Attempt to close a position that has already been closed."

        self._exit_price = price
        self._pl_realised = self._quantity * (self._exit_price - self._entry_price)
        self._pl_unrealised = 0.0
        self._is_closed = True

    def __repr__(self):
        return f'Position({self._ticker}, {self.entry_price}, {self.quantity})'


def main(ticker_list: ('The list of tickers to load data for.'),
         data_directory: ('The directory that contains the ticker data') = 'data'):
    """Simulate a trading bot that trades based on MACD crossovers and plots the estimated P/L."""
    print(ticker_list, data_directory)

    tickers = load_ticker_list(ticker_list)
    print(tickers)

    ticker_data = load_ticker_data(data_directory, tickers)

    balance = 50000

    positions: DefaultDict[Ticker, List[Position]] = defaultdict(lambda: [])
    closed_positions: DefaultDict[Ticker, List[Position]] = defaultdict(lambda: [])
    prev_close_price: Dict[Ticker, float] = dict()

    for i in range(len(ticker_data[tickers[0]]['elements']) - 2, -1, -1):
        for ticker in tickers:
            datum = ticker_data[ticker]['elements'][i]
            # previous as in data from the previous day (data is stored in reverse chronological order)
            prev_datum = ticker_data[ticker]['elements'][i + 1]

            ticker_prefix = f'[{ticker}]'
            log_prefix = f'[{datum["date_time"]}] {ticker_prefix:6s}'

            if prev_datum and datum['macd_histogram'] > 0 and datum['macd_line'] > datum['signal_line'] and prev_datum[
                'macd_line'] <= prev_datum['signal_line']:
                print(f'{log_prefix} Bullish crossover')

                market_price = datum["close"]

                if datum['macd_line'] < 0 and balance >= market_price:
                    quantity = int(0.01 * balance // market_price)
                    position = Position(ticker, market_price, quantity)
                    positions[ticker].append(position)
                    balance -= position.cost

                    print(f'{log_prefix} Buy order {quantity} share(s)@{market_price}')
            elif prev_datum and datum['macd_histogram'] < 0 and datum['macd_line'] < datum['signal_line'] and \
                    prev_datum['macd_line'] >= prev_datum['signal_line']:
                print(f'{log_prefix} Bearish crossover')

                if datum['macd_line'] > 0:
                    market_price = datum["close"]

                    num_closed_positions: int = 0
                    quantity_sold: int = 0
                    net_profit: float = 0.0
                    total_cost: float = 0.0

                    # TODO: Store positions in a data structure that allows for efficient retrieval of positions below
                    #  a given price (array-backed binary tree branching on entry price?) and efficient removal of a
                    #  given position.
                    for position in positions[ticker][:]:
                        # TODO: Potential optimisation
                        if position.entry_price < market_price:
                            position.close(market_price)

                            balance += position.exit_value
                            net_profit += position.pl_realised
                            total_cost += position.cost
                            num_closed_positions += 1
                            quantity_sold += position.quantity

                            # TODO: Potential optimisation
                            positions[ticker].remove(position)
                            closed_positions[ticker].append(position)

                    if quantity_sold > 0:
                        avg_cost = total_cost / quantity_sold
                        print(
                            f'{log_prefix} Closed {num_closed_positions} positions @ {market_price} for a net profit of '
                            f'{net_profit:.2f} (sold {quantity_sold} share(s) at an average price of '
                            f'{avg_cost:.2f}/share).')

        for ticker in tickers:
            prev_close_price[ticker] = ticker_data[ticker]['elements'][i]['close']

    portfolio_pl = dict()
    total_open_position_value: float = 0.0

    for ticker in tickers:
        total_position_cost = sum(position.cost for position in positions[ticker]) + sum(
            position.cost for position in closed_positions[ticker])
        pl_realised = sum(position.pl_realised for position in closed_positions[ticker])
        pl_unrealised = sum(position.pl_unrealised(prev_close_price[ticker]) for position in positions[ticker])
        pl_net = pl_realised + pl_unrealised

        try:
            pl_net_percentage = pl_net / total_position_cost * 100
        except ZeroDivisionError:
            pl_net_percentage = 0.0

        total_open_position_value += sum(position.quantity * prev_close_price[ticker] for position in positions[ticker])

        portfolio_pl[ticker] = pl_net

        ticker_prefix = f'[{ticker}]'
        print(
            f'{ticker_prefix:6s} P/L: {pl_net_percentage:.2f}% '
            f'({pl_net:.2f}) ({pl_realised:.2f} realised, {pl_unrealised:.2f} unrealised)')

    net_profit = sum(portfolio_pl.values())
    equity = balance + total_open_position_value

    print(f'Balance: {balance:.2f}')
    print(f'Equity: {equity:.2f}')
    # TODO: Add percentages to below stats
    print(f'Net P/L: {net_profit :.2f}')
    print(f'Mean P/L: {mean(portfolio_pl.values()):.2f}')
    print(f'Worst Performer P/L: [{min(portfolio_pl, key=portfolio_pl.get)}] {min(portfolio_pl.values()):.2f}')
    print(f'Best Performer P/L:  [{max(portfolio_pl, key=portfolio_pl.get)}] {max(portfolio_pl.values()):.2f}')


def load_ticker_data(data_directory, tickers):
    ticker_data = dict()

    for ticker in tickers:
        with open(f'{data_directory}/{ticker}/stock_price-MACD.json', 'r') as file:
            ticker_data[ticker] = json.load(file)

            if 'elements' not in ticker_data[ticker]:
                raise AttributeError(
                    f'ERROR: {data_directory}/{ticker}/stock_price-MACD.json appears to be incorrectly formatted.'
                    f'Data does not contain an "elements" property.')
    return ticker_data


def load_ticker_list(ticker_list):
    with open(ticker_list, 'r') as file:
        tickers = list(map(lambda line: line.strip(), file.readlines()))

    if len(tickers) == 0:
        raise ValueError("ERROR: Empty ticker list.")

    return tickers


if __name__ == '__main__':
    plac.call(main)
