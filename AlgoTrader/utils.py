import datetime
import json
import sqlite3
import subprocess
from typing import Set, Callable, Dict, Any

from AlgoTrader.interfaces import ITradingBot
from AlgoTrader.ticker import Ticker


def get_git_revision_hash(short=False) -> str:
    """
    Get the sha1 hash of the current revision for the git repo.
    :param short: Whether or not to generate the short hash.
    :return: the sha1 hash of the current revision.
    """
    if short:
        return subprocess.check_output(['git', 'rev-parse', '--short', 'HEAD'])
    else:
        return subprocess.check_output(['git', 'rev-parse', 'HEAD'])


def main_loop(bot: ITradingBot, tickers: Set[Ticker], yearly_contribution: float, config_file_path: str,
              fetch_data_fn: Callable[[datetime.datetime, sqlite3.Cursor], Dict[Ticker, Dict[str, Any]]]):
    """
    Test a bot on historical data and log its buy/sell actions and reports.

    :param bot: The bot to test.
    :param tickers: The tickers that the bot should buy and sell.
    :param yearly_contribution: How much cash gets added to the bot's portfolio at the start of each year.
    :param config_file_path: The path to the config file (typically config.json).
    :param fetch_data_fn: The function that fetches the data for a given day.
    """
    with open(config_file_path, 'r') as file:
        config = json.load(file)

    db_connection = sqlite3.connect(config['DATABASE_URL'])
    db_connection.row_factory = sqlite3.Row
    db_cursor = db_connection.cursor()

    db_cursor.execute('SELECT DISTINCT datetime FROM daily_stock_data ORDER BY datetime;')
    dates = list(map(lambda row: row['datetime'], db_cursor.fetchall()))

    yesterday = datetime.datetime.fromisoformat(dates[0])
    yesterdays_data = fetch_data_fn(yesterday, db_cursor)

    for i in range(1, len(dates)):
        today = datetime.datetime.fromisoformat(dates[i])
        todays_data = fetch_data_fn(today, db_cursor)

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
            bot.portfolio.print_summary(
                {ticker: yesterdays_data[ticker]['close'] for ticker in yesterdays_data}
            )

        if today.year > yesterday.year:
            bot.portfolio.add(yearly_contribution)

        yesterday = today
        yesterdays_data = todays_data

    bot.portfolio.print_summary(
        {ticker: yesterdays_data[ticker]['close'] for ticker in yesterdays_data}
    )

    db_cursor.close()
    db_connection.close()
