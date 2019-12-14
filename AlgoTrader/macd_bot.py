from typing import Dict

import plac

from AlgoTrader.core import Ticker, Position
from AlgoTrader.portfolio import Portfolio
from AlgoTrader.utils import load_ticker_data, load_ticker_list


class MACDBot:
    """
    A trading (investing?) bot that buys and sells securities based on the
    MACD (Moving Average Convergence Divergence) indicator.
    """

    def __init__(self, initial_portfolio: Portfolio):
        """
        Create a new bot.
        :param initial_portfolio: The portfolio that the bot starts with.
        """
        self.portfolio = initial_portfolio

    def update(self, ticker, datum, prev_datum):
        """
        Perform an update step where the bot may or may not open or close positions.
        :param ticker: The ticker of the security to focus on.
        :param datum: The data for the given ticker for a given day. This should include both close prices and
        MACD information.
        :param prev_datum: The data for the given ticker for the previous day.
        """
        ticker_prefix = f'[{ticker}]'
        log_prefix = f'[{datum["date_time"]}] {ticker_prefix:6s}'

        if prev_datum and datum['macd_histogram'] > 0 and datum['macd_line'] > datum['signal_line'] and prev_datum[
            'macd_line'] <= prev_datum['signal_line']:
            print(f'{log_prefix} Bullish crossover')

            market_price = datum["close"]

            if datum['macd_line'] < 0 and self.portfolio.balance >= market_price:
                quantity: int = (0.01 * self.portfolio.balance) // market_price
                position = Position(ticker, market_price, quantity)
                self.portfolio.open(position)

                print(f'{log_prefix} Opened new position: {quantity} share(s) @ {market_price}')
        elif prev_datum and datum['macd_histogram'] < 0 and datum['macd_line'] < datum['signal_line'] and \
                prev_datum['macd_line'] >= prev_datum['signal_line']:
            print(f'{log_prefix} Bearish crossover')

            if datum['macd_line'] > 0:
                market_price = datum["close"]

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


def main(ticker_list: ('The list of tickers to load data for.'),
         data_directory: ('The directory that contains the ticker data') = 'data'):
    """Simulate a trading bot that trades based on MACD crossovers and plots the estimated P/L."""
    tickers = load_ticker_list(ticker_list)
    ticker_data = load_ticker_data(data_directory, tickers)

    print(ticker_list, data_directory)
    print(tickers)

    portfolio = Portfolio(initial_balance=100000.00)
    bot = MACDBot(portfolio)

    prev_close_prices: Dict[Ticker, float] = dict()

    for i in range(len(ticker_data[tickers[0]]['elements']) - 2, -1, -1):
        for ticker in tickers:
            datum = ticker_data[ticker]['elements'][i]
            # previous as in data from the previous day (data is stored in reverse chronological order)
            prev_datum = ticker_data[ticker]['elements'][i + 1]

            bot.update(ticker, datum, prev_datum)

        for ticker in tickers:
            prev_close_prices[ticker] = ticker_data[ticker]['elements'][i]['close']

    portfolio.print_summary(prev_close_prices)


if __name__ == '__main__':
    plac.call(main)
