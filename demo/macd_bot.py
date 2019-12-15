import datetime
import json
import sqlite3

import plac

from AlgoTrader.bot import MACDBot
from AlgoTrader.portfolio import Portfolio
from AlgoTrader.ticker import load_ticker_list


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
    initial_balance=plac.Annotation('How much cash the bot starts out with', kind='option'),
    yearly_contribution=plac.Annotation('How much cash the bot adds to its portfolio on a yearly basis', kind='option')
)
def main(ticker_list: str, config_file_path: str = 'config.json',
         initial_balance: float = 100000.00, yearly_contribution=10000.0):
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

    yesterday = datetime.datetime.fromisoformat(dates[0])
    yesterdays_data = fetch_daily_data(yesterday.isoformat(), db_cursor)

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

        first_month_in_quarter = today.month % 3 == 1
        has_entered_new_month = (today.month > yesterday.month or (today.month == 1 and yesterday.month == 12))
        is_time_for_report = first_month_in_quarter and has_entered_new_month

        if is_time_for_report:
            quarter = today.month // 3
            year = today.year

            if quarter == 0:
                quarter = 4
                year -= 1

            print(f'{year} Q{quarter} Report')
            portfolio.print_summary(
                {ticker: yesterdays_data[ticker]['close'] for ticker in yesterdays_data}
            )

        if today.year > yesterday.year:
            portfolio.add(yearly_contribution)

        yesterday = today
        yesterdays_data = todays_data

    portfolio.print_summary(
        {ticker: yesterdays_data[ticker]['close'] for ticker in yesterdays_data}
    )

    db_cursor.close()
    db_connection.close()


if __name__ == '__main__':
    plac.call(main)
