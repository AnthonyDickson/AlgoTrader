Ticker = str


class Position:
    def __init__(self, ticker: Ticker, entry_price: float, quantity: int = 1):
        self._ticker: Ticker = ticker
        self._entry_price: float = entry_price
        self._exit_price: float = 0.0
        self._quantity: int = quantity
        self._pl_realised: float = 0.0
        self._pl_unrealised: float = 0.0
        self._is_closed: bool = False

    @property
    def is_closed(self) -> bool:
        return self._is_closed

    @property
    def cost(self) -> float:
        return self._quantity * self._entry_price

    entry_value = cost

    @property
    def exit_value(self) -> float:
        return self.quantity * self._exit_price

    @property
    def entry_price(self) -> float:
        return self._entry_price

    @property
    def pl_realised(self) -> float:
        return self._pl_realised

    @property
    def quantity(self):
        return self._quantity

    def pl_unrealised(self, price) -> float:
        if self._is_closed:
            return 0.0
        else:
            self._pl_unrealised = self._quantity * (price - self._entry_price)

            return self._pl_unrealised

    def close(self, price: float):
        assert self._is_closed is not True, "Attempt to close a position that has already been closed."

        self._exit_price = price
        self._pl_realised = self._quantity * (self._exit_price - self._entry_price)
        self._pl_unrealised = 0.0
        self._is_closed = True

    def __repr__(self):
        return f'Position({self._ticker}, {self.entry_price}, {self.quantity})'

    @property
    def ticker(self):
        return self._ticker
