import datetime
import sqlite3
from typing import Set, Callable, Dict, Any

from AlgoTrader.broker import Broker
from AlgoTrader.interfaces import ITradingBot
from AlgoTrader.types import Ticker


def main_loop(bot: ITradingBot, broker: Broker, tickers: Set[Ticker], initial_contribution: float,
              yearly_contribution: float,
              db_connection: sqlite3.Connection,
              fetch_data_fn: Callable[[datetime.datetime, sqlite3.Cursor], Dict[Ticker, Dict[str, Any]]]):
    """
    Test a bot on historical data and log its buy/sell actions and reports.

    :param bot: The bot to test.
    :param broker: The broker that will facilitate trades.
    :param tickers: The tickers that the bot should buy and sell.
    :param initial_contribution: How much cash the bot starts with in its portfolio.
    :param yearly_contribution: How much cash gets added to the bot's portfolio at the start of each year.
    :param db_connection: A connection to a database that can be queried for daily stock data.
    :param fetch_data_fn: The function that fetches the data for a given day.
    """
    db_cursor = db_connection.cursor()

    db_cursor.execute('SELECT DISTINCT datetime FROM daily_stock_data ORDER BY datetime;')
    dates = list(map(lambda row: row['datetime'], db_cursor.fetchall()))

    yesterday = datetime.datetime.fromisoformat(dates[0])
    yesterdays_data = fetch_data_fn(yesterday, db_cursor)

    broker.today = yesterday
    bot.portfolio_id = broker.create_portfolio(bot.name, initial_contribution)

    for i in range(1, len(dates)):
        today = datetime.datetime.fromisoformat(dates[i])
        todays_data = fetch_data_fn(today, db_cursor)

        broker.update(today)

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
            broker.print_report(bot.portfolio_id, today)

        if today.year > yesterday.year:
            broker.add_contribution(yearly_contribution, bot.portfolio_id)

        yesterday = today
        yesterdays_data = todays_data

    broker.print_report(bot.portfolio_id, yesterday)

    db_cursor.close()


def load_ticker_list(ticker_list) -> Set[Ticker]:
    """
    Load and parse a list of tickers.

    Note: The file is expected to have one ticker per line.
    :param ticker_list: The path to the file that contains the list of tickers.
    :return: A set of tickers.
    """
    with open(ticker_list, 'r') as file:
        tickers = set()

        for line in file:
            ticker = line.strip()
            ticker = ticker.replace('.', '-')
            # Manually cast to Ticker to get rid of linter warnings.
            tickers.add(Ticker(ticker))

    if len(tickers) == 0:
        raise ValueError("ERROR: Empty ticker list.")

    return tickers
