# AlgoTrader
In this project, I attempt to implement AI agents that trade US equities.

## Documentation
Documentation is hosted on [GitBook](https://app.gitbook.com/@dican732/s/algotrading/).

## Getting Started
1.  Go to [alphavantage.co](https://www.alphavantage.co/support/#api-key) and get an API key (this is free).
    Make sure you write down your API key somewhere - the only way to get it again if you forget is by emailing their 
    support team.
2.  Clone this repo:
    ```bash
    git clone https://www.github.com/eight0153/AlgoTrader.git
    cd AlgoTrader
    ```
3.  Copy and rename the example config file:
    ```bash
    cp example.config.json config.json
    ```
    and then open `config.json` with a text-editor and fill in the field `"API_KEY": ""`
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
6.  Create and initialise the database:
    ```bash
    python create_db.py
    ```
    Due to limitations on free API keys, the script can only pull down the data for two tickers per minute.
    This means that it will take about 15 minutes to download data for all of the tickers on the Dow Jones Industrial Average 
    index, and about 2 hours for the tickers in SPX.
    
    Another limitation on the API is that free API keys can only be used to make at most 500 requests per day.
    This means that if you wish to download data for all of the tickers in SPX, you will have to do this spread over 
    2-3 days. If you are going to do this, you should use the `-a` flag for each run:
    ```bash
    python create_db.py --ticker_list ticker_lists/spy.txt -a
    ```
    Without this flag, the script will delete all data in the database.
    
    Alternatively, you can download a ready-made version from [here](https://drive.google.com/file/d/10ivA-U-nbpmXK4EWsRyiOX-UhvVcyk9m/view).
    
7.  Run a demo scipt, e.g.:
    ```bash
    python -m demo.macd_trader ticker_lists/djia_tickers.txt
    ```