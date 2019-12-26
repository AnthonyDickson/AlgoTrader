import plac
import yaml

from AlgoTrader.bot import TradingBot
from AlgoTrader.broker import Broker


@plac.annotations(
    broker_config_path=plac.Annotation('The path to the config YAML file for the broker.'),
    bot_config_path=plac.Annotation('The path to the config YAML file for the bot.')
)
def main(broker_config_path: str, bot_config_path: str):
    """Backtest a trading bot."""
    with open(broker_config_path, 'r') as file:
        broker_config = yaml.safe_load(file)

    with open(bot_config_path, 'r') as file:
        bot_config = yaml.safe_load(file)

    broker = Broker.from_config(broker_config)
    bot = TradingBot.from_config(bot_config)

    bot.portfolio_id = broker.create_portfolio(bot.name, bot.initial_contribution)

    for today, yesterday in broker.iterate_dates():
        with broker:
            broker.update(today)
            bot.update(today, broker)

    broker.print_report(bot.portfolio_id, broker.today)


if __name__ == '__main__':
    plac.call(main)
