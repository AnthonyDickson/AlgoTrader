import json


def load_ticker_data(data_directory, tickers):
    ticker_data = dict()

    for ticker in tickers:
        with open(f'{data_directory}/{ticker}/stock_price-MACD.json', 'r') as file:
            ticker_data[ticker] = json.load(file)

            if 'elements' not in ticker_data[ticker]:
                raise AttributeError(
                    f'ERROR: {data_directory}/{ticker}/stock_price-MACD.json appears to be incorrectly formatted.'
                    f'Data does not contain an "elements" property.')
    return ticker_data


def load_ticker_list(ticker_list):
    with open(ticker_list, 'r') as file:
        tickers = list(map(lambda line: line.strip(), file.readlines()))

    if len(tickers) == 0:
        raise ValueError("ERROR: Empty ticker list.")

    return tickers
