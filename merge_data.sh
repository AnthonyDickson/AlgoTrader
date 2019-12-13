#!/usr/bin/env bash


usage="Usage: $(basename "$0") [-h] [-d directory] <TICKER_LIST>

Utility for merging stock price and MACD data into a single file.

Positional Parameters:
    TICKER_LIST  Text file containing the list of tickers to process.

Options:
    -h  show this help text
    -d DATA_DIRECTORY   The directory that the ticker data is saved to. (default: data/)
"

DATA_DIRECTORY=data

while getopts 'hd:' option; do
  case "$option" in
    h) echo "$usage"
       exit
       ;;
    d) DATA_DIRECTORY=${OPTARG}
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

TICKER_LIST=$1

if [[ -z ${TICKER_LIST} ]]; then
  echo "ERROR: Ticker list is empty." >&2
  exit 1
fi

while read TICKER
do
    TICKER=$(echo ${TICKER} | tr -d '\n\r')
    TICKER_DATA_DIRECTORY=${DATA_DIRECTORY}/${TICKER}

    # TODO: Allow to merge two arbitrary files?
#    FILES=($(ls ${TICKER_DATA_DIRECTORY}))
#    echo "python join_by_date.py ${TICKER_DATA_DIRECTORY}/${FILES[0]} ${TICKER_DATA_DIRECTORY}/${FILES[1]} > ${TICKER_DATA_DIRECTORY}/stock_price-MACD.json"
#    python join_by_date.py ${TICKER_DATA_DIRECTORY}/${FILES[0]} ${TICKER_DATA_DIRECTORY}/${FILES[1]} > ${TICKER_DATA_DIRECTORY}/stock_price-MACD.json

    echo "Merging ${TICKER_DATA_DIRECTORY}/stock_prices.json with ${TICKER_DATA_DIRECTORY}/MACD.json into ${TICKER_DATA_DIRECTORY}/stock_price-MACD.json"
    python join_by_date.py ${TICKER_DATA_DIRECTORY}/stock_prices.json ${TICKER_DATA_DIRECTORY}/MACD.json > ${TICKER_DATA_DIRECTORY}/stock_price-MACD.json
done < ${TICKER_LIST}

echo "Done"