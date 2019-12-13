#!/usr/bin/env bash

usage="Usage: $(basename "$0") [-h] [-o directory] [-d] <API_KEY> <TICKER_LIST>

Utility for fetching stock price and MACD data for a given list of tickers.

Positional Parameters:
    API_KEY      Your Intrinio API key.
    TICKER_LIST  Text file containing the list of tickers to fetch data for.

Options:
    -h  show this help text
    -o OUTPUT_DIRECTORY The directory to save the data to. (default: data/)
    -d DRY_RUN          Don't actually do anything.
"

OUTPUT_DIRECTORY=data
IS_DRY_RUN=false

while getopts 'ho:d' option; do
  case "$option" in
    h) echo "$usage"
       exit
       ;;
    o) OUTPUT_DIRECTORY=${OPTARG}
       ;;
    d) IS_DRY_RUN=true
       ;;
    :) printf "missing argument for -%s\n" "$OPTARG" >&2
       echo "$usage" >&2
       exit 1
       ;;
   \?) printf "illegal option: -%s\n" "$OPTARG" >&2
       echo "$usage" >&2
       exit 1
       ;;
  esac
done
shift $((OPTIND - 1))

URL=https://api-v2.intrinio.com
API_KEY=$1

if [[ -z ${API_KEY} ]]; then
  echo "ERROR: API key is empty." >&2
  exit 1
fi

TICKER_LIST=$2

if [[ -z ${TICKER_LIST} ]]; then
  echo "ERROR: Ticker list is empty." >&2
  exit 1
fi

if [[ ${IS_DRY_RUN} = true ]]; then
    echo "###########"
    echo "# DRY RUN #"
    echo "###########"
    echo

    NUM_DIRS=0
    NUM_FILES=0
fi

while read TICKER
do
    TICKER=$(echo ${TICKER} | tr -d '\n\r')
    TICKER_OUTPUT_DIRECTORY=${OUTPUT_DIRECTORY}/${TICKER}

    if [[ ${IS_DRY_RUN} = true ]]; then
        echo "Would make directory ${TICKER_OUTPUT_DIRECTORY}."
        echo "Would download ${TICKER_OUTPUT_DIRECTORY}/stock_prices.json from ${URL}/securities/${TICKER}/prices?api_key=${API_KEY}."
        echo "Would download ${TICKER_OUTPUT_DIRECTORY}/MACD.json from ${URL}/securities/${TICKER}/prices/technicals/macd?fast_period=12&slow_period=26&signal_period=9&price_key=close&page_size=100&api_key=${API_KEY}."
        echo

        NUM_DIRS=$((${NUM_DIRS} + 1))
        NUM_FILES=$((${NUM_FILES} + 2))
    else
        mkdir ${TICKER_OUTPUT_DIRECTORY}

        wget "${URL}/securities/${TICKER}/prices?api_key=${API_KEY}" -O ${TICKER_OUTPUT_DIRECTORY}/stock_prices.json
        wget "${URL}/securities/${TICKER}/prices/technicals/macd?fast_period=12&slow_period=26&signal_period=9&price_key=close&page_size=100&api_key=${API_KEY}" -O ${TICKER_OUTPUT_DIRECTORY}/MACD.json
    fi
done < ${TICKER_LIST}

if [[ ${IS_DRY_RUN} = true ]]; then
    echo "Would create ${NUM_DIRS} folders in the ${OUTPUT_DIRECTORY} folder."
    echo "Would download ${NUM_FILES} files into these folders resulting in ${NUM_FILES} API calls."
fi