import datetime
import json
import sqlite3
from typing import Set

import plac

from AlgoTrader.broker import Broker
from AlgoTrader.interfaces import ITradingBot
from AlgoTrader.types import Ticker


@plac.annotations(
    spx_tickers_file=plac.Annotation('The text file containing the current SPX ticker list.'),
    spx_changes_file=plac.Annotation('The JSON file containing the SPX ticker list diffs.'),
    spx_output_file=plac.Annotation('The JSON file to write the earliest SPX ticker list to.'),
    spx_historical_output_file=plac.Annotation('The JSON file to write the historical SPX ticker list data to.'),
    spx_all_output_file=plac.Annotation('The JSON file to write the ticker list containing the tickers of all tickers '
                                        'that have been in SPX.'),
)
def parse_historical_spx_tickers(spx_tickers_file: str, spx_changes_file: str,
                                 spx_output_file: str, spx_historical_output_file: str, spx_all_output_file: str):
    """
    Parse SPX ticker lists to produce historical SPX ticker lists.
    """
    """
    :param spx_tickers_file: The text file containing the current SPX ticker list.
    :param spx_changes_path: The JSON file containing the SPX ticker list diffs.
    :param spx_output_file: The JSON file to write the earliest SPX ticker list to.
    :param spx_historical_output_file: The JSON file to write the historical SPX ticker list data to.
    :param spx_all_output_file: The JSON file to write the ticker list containing the tickers of all tickers that have 
                                been in SPX.
    """
    spx_tickers_now = load_ticker_list(spx_tickers_file)

    with open(spx_changes_file, 'r') as file:
        spx_changes = json.load(file)

    latest = str(datetime.datetime.fromisoformat(str(datetime.date.today())))

    spx_tickers_historical = {
        'tickers': {
            latest: set(spx_tickers_now)
        }
    }

    spx_tickers_all = {
        'tickers': set(spx_tickers_now)
    }

    prev_date = latest

    for date in sorted(spx_changes, reverse=True):
        date_parts = date.split('-')
        year, month, day = map(int, date_parts)
        the_date = datetime.datetime(year, month, day)

        next_ticker_set = spx_tickers_historical['tickers'][prev_date].copy()
        spx_tickers_all['tickers'].update(next_ticker_set)

        if len(spx_changes[date]['added']['ticker']) > 0:
            next_ticker_set.difference_update([spx_changes[date]['added']['ticker']])

        if len(spx_changes[date]['removed']['ticker']) > 0:
            next_ticker_set.update([spx_changes[date]['removed']['ticker']])

        spx_tickers_historical['tickers'][str(the_date)] = set(next_ticker_set)
        prev_date = str(the_date)

    earliest_spx_date = min(spx_tickers_historical['tickers'])

    earliest_spx_tickers = {
        'tickers': {
            # Cast to list since JSON doesn't like sets.
            earliest_spx_date: list(sorted(spx_tickers_historical['tickers'][earliest_spx_date]))
        }
    }

    spx_tickers_historical['tickers'] = {
        date: list(sorted(spx_tickers_historical['tickers'][date])) for date in spx_tickers_historical['tickers']
    }

    spx_tickers_all = {
        'tickers': list(sorted(spx_tickers_all['tickers']))
    }

    with open(spx_output_file, 'w') as file:
        json.dump(earliest_spx_tickers, file)

    with open(spx_historical_output_file, 'w') as file:
        json.dump(spx_tickers_historical, file)

    with open(spx_all_output_file, 'w') as file:
        json.dump(spx_tickers_all, file)


def main_loop(bot: ITradingBot, broker: Broker, initial_contribution: float, yearly_contribution: float,
              db_connection: sqlite3.Connection):
    """
    Test a bot on historical data and log its buy/sell actions and reports.

    :param bot: The bot to test.
    :param broker: The broker that will facilitate trades.
    :param initial_contribution: How much cash the bot starts with in its portfolio.
    :param yearly_contribution: How much cash gets added to the bot's portfolio at the start of each year.
    :param db_connection: A connection to a database that can be queried for daily stock data.
    """
    dates = list(
        map(
            lambda row: row['datetime'],
            db_connection.execute('SELECT DISTINCT datetime FROM daily_stock_data ORDER BY datetime;')
        )
    )

    yesterday = datetime.datetime.fromisoformat(dates[0])

    broker.seed_data(yesterday)
    bot.portfolio_id = broker.create_portfolio(bot.name, initial_contribution)

    for i in range(1, len(dates)):
        today = datetime.datetime.fromisoformat(dates[i])

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
            broker.print_report(bot.portfolio_id, yesterday)

        with broker:
            broker.update(today)

            if today.year > yesterday.year:
                broker.add_contribution(yearly_contribution, bot.portfolio_id)

            bot.update(today)

        yesterday = today

    broker.print_report(bot.portfolio_id, yesterday)


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


def load_ticker_list_json(ticker_list) -> Set[Ticker]:
    """
    Load a JSON format list of tickers.

    Note: The file is expected to be correctly formatted JSON and have a list
    of tickers contained in a 'tickers' property.
    :param ticker_list: The path to the file that contains the list of tickers.
    :return: A set of tickers.
    """
    with open(ticker_list, 'r') as file:
        tickers = json.load(file)['tickers']

    if len(tickers) == 0:
        raise ValueError("ERROR: Empty ticker list.")

    return set(tickers)


