from AlgoTrader.types import PortfolioID, Ticker


class Position:
    def __init__(self, portfolio_id: PortfolioID, ticker: Ticker, entry_price: float, quantity: int = 1):
        """
        Enter a new position (buy an amount of a security).

        :param portfolio_id: The portfolio this position will belong to.
        :param ticker: The ticker of the security that is being bought.
        :param entry_price: The current price of the security.
        :param quantity: How many shares of the security that is being bought.
        """
        assert quantity >= 1, 'Cannot open a position with less than one share.'

        self._portfolio_id = portfolio_id
        self._ticker: Ticker = ticker
        self._quantity: int = quantity
        self._entry_price: float = entry_price
        self._exit_price: float = 0.0
        self._adjustments: float = 0.0
        self._pl_realised: float = 0.0
        self._pl_unrealised: float = 0.0
        self._is_closed: bool = False

    @property
    def portfolio_id(self) -> PortfolioID:
        """Get the ID of the portfolio that this position belongs to."""
        return self._portfolio_id

    @property
    def ticker(self) -> Ticker:
        """The ticker of the security that this position is invested in."""
        return self._ticker

    @property
    def is_closed(self) -> bool:
        """ Whether the position is closed or not (i.e. still open).
        """
        return self._is_closed

    @property
    def entry_value(self) -> float:
        """The value of the position when it was opened."""
        return self._quantity * self._entry_price

    @property
    def exit_value(self) -> float:
        """The value of the position when it was closed."""
        assert self.is_closed, 'Cannot get the exit value of a position that is still open.'

        return self.quantity * self._exit_price + self._adjustments

    @property
    def cost(self) -> float:
        """How much the position cost to open."""
        return self.entry_value

    @property
    def entry_price(self) -> float:
        """The price per share when the position was opened."""
        return self._entry_price

    @property
    def quantity(self):
        """The number of shares purchased for this position."""
        return self._quantity

    @property
    def pl_realised(self) -> float:
        """The realised profit and loss of the position."""
        assert self.is_closed is True, \
            'Cannot get the realised P&L of a position that is sill open. Use `pl_unrealised(current_price) instead.'

        return self._pl_realised + self._adjustments

    def pl_unrealised(self, current_price) -> float:
        """
        Calculate the unrealised profit and loss of the position.
        This is equal to the current value of the position minus the total cost.
        :param current_price: The current price of the security this position is invested in.
        :return: the unrealised profit and loss of the position
        """
        assert self.is_closed is False, \
            'Cannot get the unrealised P&L of a closed position. Use `pl_realised()` instead.'

        self._pl_unrealised = self._quantity * (current_price - self._entry_price)

        return self._pl_unrealised

    def current_value(self, current_price) -> float:
        """
        Calculate the current value of the position. This is equal to the current price of the security multiplied by
        the number of shares that this position is invested in.
        :param current_price: The current price of the security that this position is invested in.
        :return: the current value of the position.
        """
        assert self.is_closed is False, 'Cannot check current value on a closed position, use `exit_value` instead.'

        return self.quantity * current_price + self._adjustments

    def adjust_for_dividend(self, dividend_per_share: float):
        """
        Adjust the position value according to a given dividend amount.

        :param dividend_per_share: The dividend per share.
        :return: The total dividend this position is entitled to (quantity * dividend_amount).
        """
        assert dividend_per_share > 0, f'Cannot pay a non-positive dividend of {dividend_per_share}.'

        total_dividend_amount = self.quantity * dividend_per_share
        self._adjustments += total_dividend_amount

        return total_dividend_amount

    # TODO: Write unit tests for this...
    def adjust_for_stock_split(self, market_price: float, split_coefficient: float) -> float:
        """
        Adjust this position for a stock split.

        Note:
        - May close the position if it ends up with zero whole shares.
        - If a split results in a position with a fractional share, the fractional share is compensated with a cash
          settlement of equal value.

        :param market_price: The post-split price of the security.
        :param split_coefficient: The ratio of shares each pre-split share is now worth.
        :return: The cash settlement amount (may be zero).
        """
        assert not self.is_closed, 'Cannot adjust a closed position for stock split.'

        whole_quantity, fractional_quantity = divmod(self.quantity * split_coefficient, 1.0)

        # divmod returns a float for the quotient, so we need to explicitly cast back into an int here
        self._quantity = int(whole_quantity)

        try:
            cash_settlement_amount = fractional_quantity * market_price
        except ZeroDivisionError:
            cash_settlement_amount = 0.00

        self._adjustments += cash_settlement_amount

        if whole_quantity < 1:
            self.close(market_price)

        return cash_settlement_amount

    def close(self, price: float):
        """
        Close this position.

        :param price: The price of the security that this position is invested in at the time of closing.
        """
        assert self._is_closed is not True, "Attempt to close a position that has already been closed."

        self._exit_price = price
        self._pl_realised = self._quantity * (self._exit_price - self._entry_price)
        self._pl_unrealised = 0.0
        self._is_closed = True

    def __repr__(self):
        return (f'{self.__class__.__name__}(ticker={self._ticker}, entry_price={self.entry_price}, '
                f'quantity={self.quantity})')
