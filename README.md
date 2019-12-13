# AlgoTrader
# Getting Started
1.  You need to make an account with [Intrinio](https://intrinio.com/) and get an API key (this is free).
2.  Clone this repo:
    ```bash
    git clone https://www.github.com/eight0153/AlgoTrader.git
    cd AlgoTrader
    ```
3.  Fetch some ticker data:
    ```bash
    ./fetch_data.sh <YOUR_API_KEY> data/djia_tickers.txt
    ```
    The ticker list in this example lists the companies listed in the Dow Jones Industrial Average which are free to access (other tickers require a paid subscription).
    -   You can create your own ticker list by simply creating a text document with a ticker per line.
4.  Process the data:
    ```bash
    ./merge_data.sh data/djia_tickers.txt
    ```