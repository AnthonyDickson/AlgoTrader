# AlgoTrader
# Getting Started
1.  Make an account at [intrinio.com](https://intrinio.com/) to get an API key (this is free).
2.  Clone this repo:
    ```bash
    git clone https://www.github.com/eight0153/AlgoTrader.git
    cd AlgoTrader
    ```
3.  Copy and rename the example config file:
    ```bash
    cp example.config.json config.json
    ```
    and then open `config.json` with a text-editor and fill in the field `"API_KEY": ""` with your API key.
    Your API keys can be found at [account.intrinio.com](https://account.intrinio.com/account/access_keys).
    Unless you are a paid subscriber to the relevant data feeds, you should use your sandbox key.
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
    This may take about 5 minutes depending on your internet connection.
    
7.  Run a demo scipt, e.g.:
    ```bash
    python -m AlgoTrader.macd_trader djia_tickers.txt
    ```