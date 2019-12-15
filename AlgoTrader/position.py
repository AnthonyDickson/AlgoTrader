from AlgoTrader.ticker import Ticker


class Position:
    def __init__(self, ticker: Ticker, entry_price: float, quantity: int = 1):
        """
        Enter a new position (buy an amount of a security).
        :param ticker: The ticker of the security that is being bought.
        :param entry_price: The current price of the security.
        :param quantity: How many shares of the security that is being bought.
        """
        assert quantity >= 1, 'Cannot open a position with less than one share.'

        self._ticker: Ticker = ticker
        self._entry_price: float = entry_price
        self._exit_price: float = 0.0
        self._quantity: int = quantity
        self._pl_realised: float = 0.0
        self._pl_unrealised: float = 0.0
        self._is_closed: bool = False

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
        assert self.is_closed is True, 'Cannot get the exit value of a position that is still open.'

        return self.quantity * self._exit_price

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

        return self._pl_realised

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

        return self.quantity * current_price

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
