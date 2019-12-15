import datetime
from typing import Union

import plac

from AlgoTrader.bot import BuyAndHoldBot, BuyPeriod
from AlgoTrader.portfolio import Portfolio
from AlgoTrader.ticker import Ticker
from AlgoTrader.utils import main_loop


def fetch_daily_data(date: datetime.datetime, db_cursor):
    db_cursor.execute('SELECT ticker, datetime, close, macd_histogram, macd_line, signal_line '
                      'FROM daily_stock_data '
                      'WHERE ticker = ? AND datetime = ?', ('SPY', date.isoformat(),))

    yesterdays_data = {row['ticker']: {key: row[key] for key in row.keys()} for row in db_cursor}

    return yesterdays_data


# TODO: Adjust for stock splits.
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

    portfolio = Portfolio(initial_balance=initial_balance)
    bot = BuyAndHoldBot(portfolio, buy_period=buy_period)

    main_loop(bot, tickers, yearly_contribution, config_file_path, fetch_daily_data)


if __name__ == '__main__':
    plac.call(main)
