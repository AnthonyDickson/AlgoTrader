import datetime
import json
import sqlite3
import sys
import time

import plac
import requests

from AlgoTrader.utils import load_ticker_list


def log(msg: str, msg_type='INFO', inplace=False):
    assert msg_type in ('INFO', 'WARNING', 'ERROR')

    msg = f'[{datetime.datetime.now()}] {msg_type}: {msg}'

    file = sys.stdout if msg_type == 'INFO' else sys.stderr

    if inplace:
        msg = '\r' + msg
        end = ''
    else:
        end = '\n'

    print(msg, file=file, end=end)


def get_earliest_date(api_url):
    """
    Test the API and also get the earliest date for which both stock price and MACD data is available.
    :param api_url: The API url.
    :return: the earliest date for which both stock price and MACD data is available.
    """
    stock_price_payload = {
        'function': 'TIME_SERIES_DAILY_ADJUSTED',
        'symbol': 'MSFT',
        'outputsize': 'full',
        'apikey': 'demo'
    }

    r = requests.get(api_url, params=stock_price_payload)
    r.raise_for_status()
    stock_price_data = r.json()

    macd_payload = {
        'function': 'MACD',
        'symbol': 'MSFT',
        'interval': 'daily',
        'series_type': 'open',
        'apikey': 'demo'
    }

    r = requests.get(api_url, params=macd_payload)
    r.raise_for_status()
    macd_data = r.json()

    return max(min(stock_price_data['Time Series (Daily)']), min(macd_data['Technical Analysis: MACD']))


def gen_rows(stock_price_data, macd_data, from_date):
    ticker = stock_price_data['Meta Data']['2. Symbol']
    macd_ticker = macd_data['Meta Data']['1: Symbol']

    assert ticker == macd_ticker, "Both data sources must be for the same ticker."

    for date in filter(lambda datum_date: datum_date >= from_date, stock_price_data['Time Series (Daily)'].keys()):
        # TODO: Allow for MACD data to be nullable, and make bots handle the case where specific data is not available.
        try:
            stock_price_datum = stock_price_data['Time Series (Daily)'][date]
            macd_datum = macd_data['Technical Analysis: MACD'][date]
        except KeyError:
            if date not in stock_price_data['Time Series (Daily)']:
                log(f'Stock data for {ticker} on {date} is missing, skipping this day\'s data.', msg_type='WARNING')

            if date not in macd_data['Technical Analysis: MACD']:
                log(f'Technical (MACD) data for {ticker} on {date} is missing, skipping this day\'s data.',
                    msg_type='WARNING')

            continue

        yield (
            ticker,
            datetime.datetime.fromisoformat(date),  # Normalise dates to include time (defaults to midnight)
            stock_price_datum['1. open'],
            stock_price_datum['2. high'],
            stock_price_datum['3. low'],
            stock_price_datum['4. close'],
            stock_price_datum['5. adjusted close'],
            stock_price_datum['6. volume'],
            stock_price_datum['7. dividend amount'],
            stock_price_datum['8. split coefficient'],
            macd_datum['MACD_Hist'],
            macd_datum['MACD'],
            macd_datum['MACD_Signal']
        )


@plac.annotations(
    ticker_list=plac.Annotation('The path to a text file containing a list of tickers to download data for.',
                                kind='option', abbrev='t'),
    config_file=plac.Annotation('The path to the JSON file that contains the config data.',
                                kind='option', abbrev='c'),
    max_requests_per_minute=plac.Annotation('The maximum number of requests per minute. '
                                            'Free uses of Alpha Vantage are limited to 5 requests per minute.',
                                            kind='option', abbrev='m'),
    append=plac.Annotation('Flag indicating that the database should not be created from scratch, '
                           'allowing for data to added to an existing database.',
                           kind='flag', abbrev='a')
)
def main(ticker_list: str = 'ticker_lists/djia.txt', config_file: str = 'config.json',
         max_requests_per_minute: int = 5, append: bool = False):
    """
    Create and populate a SQLite database from API data.

    Note: The default behaviour of this script is to overwrite the database at the specified URL in the config file if
    it already exists. If you want to add data to an existing database, make sure to use the '-a' flag.
    """
    start = time.time()

    with open(config_file, 'r') as file:
        config = json.load(file)

    tickers = load_ticker_list(ticker_list)

    api_url = 'https://www.alphavantage.co/query'
    earliest_date = get_earliest_date(api_url)

    db_connection = sqlite3.connect(config['DATABASE_URL'])
    db_cursor = db_connection.cursor()

    if not append:
        with open(config['DATABASE_NUKE_SCRIPT'], 'r') as file:
            db_cursor.executescript(file.read())

    with open(config['DATABASE_CREATE_SCRIPT'], 'r') as file:
        db_cursor.executescript(file.read())

    batch_start = time.time()
    num_requests_for_batch = 0
    num_tickers_processed = 0

    for ticker in tickers:
        ticker_start = time.time()

        stock_price_payload = {
            'function': 'TIME_SERIES_DAILY_ADJUSTED',
            'symbol': ticker,
            'outputsize': 'full',
            'apikey': config['API_KEY']
        }

        macd_payload = {
            'function': 'MACD',
            'symbol': ticker,
            'interval': 'daily',
            'series_type': 'close',
            'apikey': config['API_KEY']
        }

        if num_requests_for_batch + 2 > max_requests_per_minute:
            log(f'Reached maximum number requests for time period ({max_requests_per_minute}/minute).')

            time_to_wait = 60 - int(time.time() - batch_start) + 3
            time_left = time_to_wait

            while time_left > 0:
                log(f'Waiting for {time_left:02d}s...', inplace=True)
                time.sleep(1.0)
                time_left -= 1

            log(f'Waited for {time_to_wait:02d}s\n', inplace=True)
            batch_start = time.time()
            ticker_start = time.time()
            num_requests_for_batch = 0

        log(f'Fetching data for {ticker}... ')

        try:
            r = requests.get(api_url, params=stock_price_payload)
            r.raise_for_status()
            stock_price_data = r.json()

            r = requests.get(api_url, params=macd_payload)
            r.raise_for_status()
            macd_data = r.json()
        except requests.exceptions.HTTPError as e:
            db_connection.rollback()

            log(f'HTTP {e}', msg_type='ERROR')

            if e.response.status_code == 503:
                log(f'It is likely that you have hit your daily API limit.', msg_type='ERROR')

            break

        num_requests_for_batch += 2

        db_cursor.executemany('''
        INSERT OR IGNORE INTO daily_stock_data 
            (ticker, datetime, open, high, low, close, adjusted_close, volume, dividend_amount, split_coefficient, 
                macd_histogram, macd_line, signal_line) 
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', gen_rows(stock_price_data, macd_data, from_date=earliest_date))

        db_connection.commit()

        num_tickers_processed += 1
        ticker_elapsed_time = time.time() - ticker_start
        elapsed_time_str = time.strftime("%H:%M:%S", time.gmtime(ticker_elapsed_time))
        log(f'Processed data for {ticker} in {elapsed_time_str}')

    db_connection.commit()
    db_cursor.close()
    db_connection.close()

    elapsed_time = time.strftime("%H:%M:%S", time.gmtime(time.time() - start))
    log(f'Processed data for {num_tickers_processed} tickers in {elapsed_time}\n')


if __name__ == '__main__':
    plac.call(main)
