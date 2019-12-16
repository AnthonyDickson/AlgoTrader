import datetime
import json
import sqlite3

import plac

from AlgoTrader.bot import MACDBot
from AlgoTrader.broker import Broker
from AlgoTrader.utils import main_loop, load_ticker_list


def fetch_daily_data(date: datetime.datetime, db_cursor):
    db_cursor.execute('SELECT ticker, datetime, close, macd_histogram, macd_line, signal_line '
                      'FROM daily_stock_data '
                      'WHERE datetime = ?', (date.isoformat(),))

    yesterdays_data = {row['ticker']: {key: row[key] for key in row.keys()} for row in db_cursor}

    return yesterdays_data


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

    broker = Broker(db_connection)
    bot = MACDBot(broker)
    bot.portfolio_id = broker.create_portfolio(bot.name, initial_balance)

    main_loop(bot, broker, tickers, yearly_contribution, db_connection, fetch_daily_data)

    db_connection.close()


if __name__ == '__main__':
    plac.call(main)
