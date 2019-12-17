import datetime
import json
import sqlite3
from typing import Union

import plac

from AlgoTrader.bot import BuyAndHoldBot, BuyPeriod
from AlgoTrader.broker import Broker
from AlgoTrader.types import Ticker
from AlgoTrader.utils import main_loop


def fetch_daily_data(date: datetime.datetime, db_cursor):
    db_cursor.execute('SELECT ticker, datetime, close, macd_histogram, macd_line, signal_line '
                      'FROM daily_stock_data '
                      'WHERE ticker = ? AND datetime = ?', ('SPY', date,))

    yesterdays_data = {row['ticker']: {key: row[key] for key in row.keys()} for row in db_cursor}

    return yesterdays_data


@plac.annotations(
    config_file_path=plac.Annotation('The path to the JSON file that contains the config data.'),
    initial_balance=plac.Annotation('How much cash the bot starts out with',
                                    kind='option', abbrev='i'),
    yearly_contribution=plac.Annotation('How much cash the bot adds to its portfolio on a yearly basis',
                                        kind='option', abbrev='c'),
    buy_period=plac.Annotation('How often the bot attempts to buy into SPY.',
                               kind='option', abbrev='p', choices=[period.name for period in BuyPeriod], type=str),

)
def main(config_file_path: str = 'config.json', initial_balance: float = 100000.00, yearly_contribution=10000.0,
         buy_period: Union[str, BuyPeriod] = BuyPeriod.WEEKLY.name):
    """Simulate a trading bot that simply buys SPY periodically and holds."""
    tickers = {Ticker('SPY')}

    print(config_file_path, buy_period)
    print(tickers)

    if type(buy_period) is str:
        buy_period = {period.name: period for period in BuyPeriod}[buy_period]

    with open(config_file_path, 'r') as file:
        config = json.load(file)

    db_connection = sqlite3.connect(config['DATABASE_URL'])
    db_connection.row_factory = sqlite3.Row

    try:
        broker = Broker(db_connection)
        bot = BuyAndHoldBot(broker, buy_period)

        main_loop(bot, broker, tickers, initial_balance, yearly_contribution, db_connection, fetch_daily_data)
    finally:
        db_connection.close()


if __name__ == '__main__':
    plac.call(main)
