from typing import Set


class Ticker(str):
    """Represents a stock/security ticker."""


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
