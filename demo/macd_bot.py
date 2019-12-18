import datetime
import json
import sqlite3

import plac

from AlgoTrader.bot import MACDBot
from AlgoTrader.broker import Broker
from AlgoTrader.utils import main_loop


def fetch_daily_data(date: datetime.datetime, db_cursor):
    db_cursor.execute('SELECT ticker, datetime, close, macd_histogram, macd_line, signal_line '
                      'FROM daily_stock_data '
                      'WHERE datetime = ?', (date,))

    yesterdays_data = {row['ticker']: {key: row[key] for key in row.keys()} for row in db_cursor}

    return yesterdays_data


@plac.annotations(
    historical_tickers_list=plac.Annotation('The path to the JSON file that contains the historical SPX ticker lists.'),
    config_file_path=plac.Annotation('The path to the JSON file that contains the config data.'),
    initial_balance=plac.Annotation('How much cash the bot starts out with', kind='option'),
    yearly_contribution=plac.Annotation('How much cash the bot adds to its portfolio on a yearly basis', kind='option')
)
def main(historical_tickers_list: str, config_file_path: str = 'config.json',
         initial_balance: float = 100000.00, yearly_contribution=10000.0):
    """Simulate a trading bot that trades based on MACD crossovers and plots the estimated P/L."""
    with open(historical_tickers_list, 'r') as file:
        historical_tickers = json.load(file)

        historical_tickers['tickers'] = {
            str(date): set(historical_tickers['tickers'][str(date)]) for date in historical_tickers['tickers']
        }

    print(historical_tickers_list, config_file_path)

    with open(config_file_path, 'r') as file:
        config = json.load(file)

    db_connection = sqlite3.connect(config['DATABASE_URL'])
    db_connection.row_factory = sqlite3.Row

    try:
        broker = Broker(db_connection)
        bot = MACDBot(broker, historical_tickers)

        main_loop(bot, broker, initial_balance, yearly_contribution, db_connection)
    finally:
        db_connection.close()


if __name__ == '__main__':
    plac.call(main)
