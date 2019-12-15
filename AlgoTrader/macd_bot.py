import datetime
import json
import sqlite3

import plac

from AlgoTrader.core import Position
from AlgoTrader.portfolio import Portfolio
from AlgoTrader.utils import load_ticker_list


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
        log_prefix = f'[{datum["datetime"]}] {ticker_prefix:6s}'

        if prev_datum and datum['macd_histogram'] > 0 and datum['macd_line'] > datum['signal_line'] and prev_datum[
            'macd_line'] <= prev_datum['signal_line']:
            market_price = datum['close']

            if datum['macd_line'] < 0 and self.portfolio.balance >= market_price:
                quantity: int = (0.01 * self.portfolio.balance) // market_price
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


def fetch_daily_data(date, db_cursor):
    db_cursor.execute('SELECT ticker, datetime, close, macd_histogram, macd_line, signal_line '
                      'FROM daily_stock_data '
                      'WHERE datetime = ?', (date,))
    yesterdays_data = {row['ticker']: {key: row[key] for key in row.keys()} for row in db_cursor}
    return yesterdays_data


# TODO: Adjust for stock splits.
@plac.annotations(
    ticker_list=plac.Annotation('The list of tickers to load data for.'),
    config_file_path=plac.Annotation('The path to the JSON file that contains the config data.'),
    initial_balance=plac.Annotation('How much cash the bot starts out with', kind='option')
)
def main(ticker_list: str, config_file_path: str = 'config.json', initial_balance: float = 100000.00):
    """Simulate a trading bot that trades based on MACD crossovers and plots the estimated P/L."""
    tickers = load_ticker_list(ticker_list)

    print(ticker_list, config_file_path)
    print(tickers)

    with open(config_file_path, 'r') as file:
        config = json.load(file)

    db_connection = sqlite3.connect(config['DATABASE_URL'])
    db_connection.row_factory = sqlite3.Row
    db_cursor = db_connection.cursor()

    db_cursor.execute('SELECT DISTINCT datetime FROM daily_stock_data ORDER BY datetime;')
    dates = list(map(lambda row: row['datetime'], db_cursor.fetchall()))

    yesterdays_data = fetch_daily_data(dates[0], db_cursor)

    portfolio = Portfolio(initial_balance=initial_balance)
    bot = MACDBot(portfolio)

    for i in range(1, len(dates)):
        today = datetime.datetime.fromisoformat(dates[i])
        todays_data = fetch_daily_data(today.isoformat(), db_cursor)

        for ticker in tickers:
            try:
                datum = todays_data[ticker]
                prev_datum = yesterdays_data[ticker]
            except KeyError:
                continue

            bot.update(ticker, datum, prev_datum)

        # TODO: Fix missing reports - first of month doesn't always land on a weekday.
        #  Should make sure day is first weekday of month.
        if today.month % 3 == 1 and today.day == 1:
            quarter = today.month // 3
            year = today.year

            if quarter == 0:
                quarter = 4
                year -= 1

            print(f'Q{quarter} {year} Report')
            portfolio.print_summary(
                {ticker: yesterdays_data[ticker]['close'] for ticker in yesterdays_data}
            )

        yesterdays_data = todays_data

    portfolio.print_summary(
        {ticker: yesterdays_data[ticker]['close'] for ticker in yesterdays_data}
    )

    db_cursor.close()
    db_connection.close()


if __name__ == '__main__':
    plac.call(main)
