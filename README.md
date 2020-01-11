# AlgoTrader
In this project, I attempt to implement simple AI agents that trade US equities in a simulated environment.

The agents use one of two strategies:
1.  buy and hold;
2.  momentum trading.

A bot following the buy and hold strategy will simply buy stocks periodically and hold them.
A bot following the momentum trading strategy will buy and sell stocks based on crossovers in the MACD indicator.

The backtesting environment uses historical stock data (inluding stock splits and dividends) from 2000 to 2019 and taxes are also estimated using historical ordinary and capital gains rates in order to calculate more realistic returns.

The best configuration that was tested used the config file [demo/macd_config-200percent.yml](https://github.com/eight0153/AlgoTrader/blob/master/demo/macd_config-200percent.yml) and was able to achieve a [CAGR](https://en.wikipedia.org/wiki/Compound_annual_growth_rate) of about 9% over a 20 year period in the backtesting environment.
Empirical results for all configurations found in the [demo/](https://github.com/eight0153/AlgoTrader/blob/master/demo) folder are shown in the notebook [notebooks/portfolio_performance_viz.ipynb](https://github.com/eight0153/AlgoTrader/blob/master/notebooks/portfolio_performance_viz.ipynb).
These results were generated using the scripts, ticker lists and configuration files found in [this revision](https://github.com/eight0153/AlgoTrader/tree/d5651a184453523916704fbdf130fd7bc8635f72) of the repositiory.

## Getting Started
1.  Clone this repo:
    ```bash
    git clone https://www.github.com/eight0153/AlgoTrader.git
    cd AlgoTrader
    ```
2.  Copy and rename the template config file:
    ```bash
    cp example.config.yml config.yml
    ```
3.  Download a copy of a database containing historical stock data:
    ```bash
    wget http://algotrader-data.s3.amazonaws.com/data.db
    ```
    This database contains historical stock data from near the start of 2000 up until 20 December 2019 sourced from [alphavantage.co](https://www.alphavantage.co/).
    If you want more up-to-date data then follow the steps in the sections below for building the database from scratch and creating an updated historical SPX tickers list.
4.  Setup the conda environment:
    ```bash
    conda env create -f environment.yml
    ```
    You can get conda installed on your machine by following the instructions at 
    [docs.conda.io](https://docs.conda.io/projects/conda/en/latest/user-guide/install/index.html).   
5.  Before you run any python code, activate the conda environment.
    ```bash
    conda activate AlgoTrader
    ```
6.  Run a demo script, e.g.:
    ```bash
    python -m demo.backtest demo/broker_config.yml demo/macd_config.yml
    ```
### Building the Database
1.  Go to [alphavantage.co](https://www.alphavantage.co/support/#api-key) and get an API key (this is free).
    Make sure you write down your API key somewhere - the only way to get it again if you forget is by emailing their 
    support team.
2.  Open your `config.yml` with a text-editor and fill in the field `API_KEY: ` with your API key.
3.  Create and initialise the database:
    ```bash
    python create_db.py
    ```
    Due to limitations on free API keys, the script can only pull down the data for two tickers per minute.
    This means that it will take about 15 minutes to download data for all of the tickers on the Dow Jones Industrial Average 
    index, and about 2 hours for the tickers in SPX.
    
    Another limitation on the API, according to the documentation, is that free API keys can only be used to make at most 500 requests per day.
    This means that if you wish to download data for all of the tickers in SPX, you will have to do this spread over 
    2-3 days. If you are going to do this, you should use the `-a` flag for each run:
    ```bash
    python create_db.py --ticker_list ticker_lists/spy.json -a
    ```
    Without this flag, the script will delete all data in the database from previous runs.
    **NOTE**: Although this limitation is mentioned on the API documentation webpage, this limit did not appear to be enforced  
    the last time this code was run (December, 2019).
    
### Backtesting Environment
One note about the backtesting environment is that it relies on knowing how the Spyder S&P 500 index (SPX) changed (i.e. its historical components).
The JSON file containing the data on these changes was scraped from [wikipedia.org/wiki/List_of_S&P_500_companies](https://en.wikipedia.org/wiki/List_of_S%26P_500_companies), in particular [this table](https://en.wikipedia.org/wiki/List_of_S%26P_500_companies#Selected_changes_to_the_list_of_S&P_500_components) was parsed and dumped as a JSON file.
You can check the expected format in [ticker_lists/sp500-historical-components.json](https://github.com/eight0153/AlgoTrader/blob/master/ticker_lists/sp500-historical-components.json).

The JSON ticker lists required by the backtesting script can be constructed using the script [demo/parse_historical_spx_tickers.py](https://github.com/eight0153/AlgoTrader/blob/master/demo/parse_historical_spx_tickers.py).
This script also requires the current SPX components as a text file.
The text file should contain one ticker per line and any tickers containing a period (e.g. 'BRK.B') must have the period replaced by a hyphen (e.g. 'BRK.B' would be changed to 'BRK-B').
The current SPX components were scraped from [this table](https://en.wikipedia.org/wiki/List_of_S%26P_500_companies#S&P_500_component_stocks).
