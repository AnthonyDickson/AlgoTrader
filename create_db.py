import datetime
import json
import sqlite3
import time

import intrinio_sdk
import plac
from intrinio_sdk import ApiResponseSecurityStockPrices, ApiResponseSecurityMovingAverageConvergenceDivergence
from intrinio_sdk.rest import ApiException

from AlgoTrader.utils import load_ticker_list


def gen_rows(stock_prices: ApiResponseSecurityStockPrices, macd: ApiResponseSecurityMovingAverageConvergenceDivergence):
    for stock_price_data, macd_data in zip(stock_prices.stock_prices, macd.technicals):
        yield (
            stock_prices.security.ticker,
            datetime.datetime.combine(stock_price_data.date, datetime.time()).timestamp(),
            stock_price_data.close,
            macd_data.macd_histogram,
            macd_data.macd_line,
            macd_data.signal_line
        )


def main(config_file_path: "The path to the JSON file that contains the config data." = 'config.json',
         ticker_list: "The path to a text file containing a list of tickers to download data for." = 'djia_tickers.txt',
         num_pages_to_fetch: "The number of pages of data to fetch for each ticker" = 20):
    with open(config_file_path, 'r') as file:
        config = json.load(file)

    intrinio_sdk.ApiClient().configuration.api_key['api_key'] = config['API_KEY']
    tickers = load_ticker_list(ticker_list)

    with open(config['DATABASE_CREATE_SCRIPT'], 'r') as file:
        create_db_sql = file.read()

    conn = sqlite3.connect(config['DATABASE_URL'])
    cursor = conn.cursor()
    cursor.executescript(create_db_sql)
    security_api = intrinio_sdk.SecurityApi()
    technicals_api = intrinio_sdk.TechnicalApi()
    start = time.time()

    for ticker in tickers:
        ticker_start = time.time()
        securities_next_page = ''
        technicals_next_page = ''

        page = 0

        while page < num_pages_to_fetch and securities_next_page is not None and technicals_next_page is not None:
            print(f'\rProcessing page {page + 1:02d} of data for {ticker}...', end='')
            try:
                stock_prices: ApiResponseSecurityStockPrices = \
                    security_api.get_security_stock_prices(ticker, next_page=securities_next_page)

                macd: ApiResponseSecurityMovingAverageConvergenceDivergence = \
                    technicals_api.get_security_price_technicals_macd(ticker, next_page=technicals_next_page)

                securities_next_page = stock_prices.next_page
                technicals_next_page = macd.next_page
                page += 1

                cursor.executemany('''
                INSERT INTO stock_data (ticker, date, close_price, macd_histogram, macd_line, signal_line) VALUES (?, ?, ?, ?, ?, ?)
                ''', gen_rows(stock_prices, macd))
                # Save (commit) the changes
                conn.commit()
            except ApiException as e:
                print("Exception when calling SecurityApi->get_security_stock_prices: %s\r\n" % e)

        ticker_elapsed_time = time.time() - ticker_start
        elapsed_time_str = time.strftime("%H:%M:%S", time.gmtime(ticker_elapsed_time))
        print(f'\rProcessed {page:02d} pages of data for {ticker} in {elapsed_time_str}')

    conn.commit()
    cursor.close()
    # We can also close the connection if we are done with it.
    # Just be sure any changes have been committed or they will be lost.
    conn.close()

    elapsed_time = time.strftime("%H:%M:%S", time.gmtime(time.time() - start))
    print(f'Processed data for {len(tickers)} tickers in {elapsed_time}')
    print()


if __name__ == '__main__':
    plac.call(main)
