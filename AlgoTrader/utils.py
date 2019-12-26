import datetime
import json
import re
from typing import Set

import plac

from AlgoTrader.exceptions import InvalidFrequencyFormatError
from AlgoTrader.types import Ticker, Period


@plac.annotations(
    spx_tickers_file=plac.Annotation('The JSON file containing the current SPX ticker list.'),
    spx_changes_file=plac.Annotation('The JSON file containing the SPX ticker list diffs.'),
    spx_output_file=plac.Annotation('The JSON file to write the earliest SPX ticker list to.'),
    spx_historical_output_file=plac.Annotation('The JSON file to write the historical SPX ticker list data to.'),
    spx_all_output_file=plac.Annotation('The JSON file to write the ticker list containing the tickers of all tickers '
                                        'that have been in SPX.'),
)
def parse_historical_spx_tickers(spx_tickers_file: str, spx_changes_file: str,
                                 spx_output_file: str, spx_historical_output_file: str, spx_all_output_file: str):
    """
    Parse SPX ticker lists to produce historical SPX ticker lists.
    """
    """
    :param spx_tickers_file: The text file containing the current SPX ticker list.
    :param spx_changes_path: The JSON file containing the SPX ticker list diffs.
    :param spx_output_file: The JSON file to write the earliest SPX ticker list to.
    :param spx_historical_output_file: The JSON file to write the historical SPX ticker list data to.
    :param spx_all_output_file: The JSON file to write the ticker list containing the tickers of all tickers that have 
                                been in SPX.
    """
    spx_tickers_now = load_ticker_list_json(spx_tickers_file)

    with open(spx_changes_file, 'r') as file:
        spx_changes = json.load(file)

    latest = str(datetime.datetime.fromisoformat(str(datetime.date.today())))

    spx_tickers_historical = {
        'tickers': {
            latest: set(spx_tickers_now)
        }
    }

    spx_tickers_all = {
        'tickers': set(spx_tickers_now)
    }

    prev_date = latest

    for date in sorted(spx_changes, reverse=True):
        date_parts = date.split('-')
        year, month, day = map(int, date_parts)
        the_date = datetime.datetime(year, month, day)

        next_ticker_set = spx_tickers_historical['tickers'][prev_date].copy()
        spx_tickers_all['tickers'].update(next_ticker_set)

        if len(spx_changes[date]['added']['ticker']) > 0:
            next_ticker_set.difference_update([spx_changes[date]['added']['ticker']])

        if len(spx_changes[date]['removed']['ticker']) > 0:
            next_ticker_set.update([spx_changes[date]['removed']['ticker']])

        spx_tickers_historical['tickers'][str(the_date)] = set(next_ticker_set)
        prev_date = str(the_date)

    earliest_spx_date = min(spx_tickers_historical['tickers'])

    earliest_spx_tickers = {
        'tickers': {
            # Cast to list since JSON doesn't like sets.
            earliest_spx_date: list(sorted(spx_tickers_historical['tickers'][earliest_spx_date]))
        }
    }

    spx_tickers_historical['tickers'] = {
        date: list(sorted(spx_tickers_historical['tickers'][date])) for date in spx_tickers_historical['tickers']
    }

    spx_tickers_all = {
        'tickers': list(sorted(spx_tickers_all['tickers']))
    }

    with open(spx_output_file, 'w') as file:
        json.dump(earliest_spx_tickers, file)

    with open(spx_historical_output_file, 'w') as file:
        json.dump(spx_tickers_historical, file)

    with open(spx_all_output_file, 'w') as file:
        json.dump(spx_tickers_all, file)


def load_ticker_list_json(ticker_list) -> Set[Ticker]:
    """
    Load a JSON format list of tickers.

    Note: The file is expected to be correctly formatted JSON and have a list
    of tickers contained in a 'tickers' property.
    :param ticker_list: The path to the file that contains the list of tickers.
    :return: A set of tickers.
    """
    with open(ticker_list, 'r') as file:
        tickers = json.load(file)['tickers']
        tickers = set(map(lambda ticker: ticker.replace('.', '-'), tickers))

    if len(tickers) == 0:
        raise ValueError("ERROR: Empty ticker list.")

    return tickers


class Scheduler:
    """An object for scheduling tasks."""

    def __init__(self, period: Period, frequency: int):
        """
        Create a new scheduler.

        :param period: The period between tasks.
        :param frequency: A multiplier for `period`.
        """
        assert frequency >= 1, "Frequency must be a positive integer."

        self.period = period
        self.frequency = frequency

    def has_period_elapsed(self, current_date: datetime.datetime,
                           previous_elapsed_date: datetime.datetime = datetime.datetime.fromtimestamp(0.0)):
        """
        Check if the scheduled period has elapsed or not.

        :param current_date: The current date.
        :param previous_elapsed_date: The date when the scheduled period last elapsed.
        :return: True if the scheduled period has elapsed, False otherwise.
        """
        if self.period == Period.QUARTERLY:
            first_month_in_quarter = current_date.month % 3 == 1
            has_entered_new_month = (current_date.month > previous_elapsed_date.month or
                                     current_date.year > previous_elapsed_date.year)

            months_between = (current_date.year - previous_elapsed_date.year) * 12 + \
                             (current_date.month - previous_elapsed_date.month)
            quarters_elapsed = months_between / 3
            period_elapsed = first_month_in_quarter and has_entered_new_month and quarters_elapsed >= self.frequency
        else:
            days_elapsed = (current_date - previous_elapsed_date).days
            weeks_elapsed = days_elapsed / 7
            years_elapsed = days_elapsed / 365.25
            months_elapsed = years_elapsed * 12

            period_elapsed = self.period == Period.DAILY and days_elapsed >= self.frequency
            period_elapsed |= self.period == Period.WEEKLY and weeks_elapsed >= self.frequency
            period_elapsed |= self.period == Period.MONTHLY and months_elapsed >= self.frequency
            period_elapsed |= self.period == Period.YEARLY and years_elapsed >= self.frequency

        return period_elapsed

    @staticmethod
    def from_string(schedule_string: str) -> 'Scheduler':
        """
        Create a Scheduler from a string.

        :param schedule_string: The schedule format string.
        Valid formats for frequencies/time periods is an integer followed by: 'd' for day, 'm' for month',
        'q' for quarter or 'y' for year. For example, '5d' would be five days, '2w' would be two weeks and '1y' would
        be one year.
        :return: The constructed Scheduler object.
        :raises: InvalidFrequencyFormatError if the given format string is not valid.
        """
        # noinspection SpellCheckingInspection
        valid_periods = 'dwmqy'

        # noinspection SpellCheckingInspection
        frequency_pattern = re.compile(r"^(\d+)([dwmqy])$")

        match = re.match(frequency_pattern, schedule_string)

        error_message = f"Invalid schedule string format '{schedule_string}'. Valid format is a positive " \
                        f"integer followed by one of: [{', '.join(valid_periods)} - e.g. '1{valid_periods[0]}'."
        try:
            frequency = int(match.group(1))
            period = str(match.group(2))
        except AttributeError:
            # AttributeError raised if match returns None (i.e. no match).
            raise InvalidFrequencyFormatError(error_message)

        # noinspection SpellCheckingInspection
        if frequency < 1:
            raise InvalidFrequencyFormatError(error_message)

        if period == 'd':
            period = Period.DAILY
        elif period == 'w':
            period = Period.WEEKLY
        elif period == 'm':
            period = Period.MONTHLY
        elif period == 'q':
            period = Period.QUARTERLY
        elif period == 'y':
            period = Period.YEARLY
        else:
            raise InvalidFrequencyFormatError(error_message)

        return Scheduler(period, frequency)
