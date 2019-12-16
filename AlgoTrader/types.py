import hashlib

from AlgoTrader.exceptions import InvalidPortfolioIDError


class PortfolioID(str):
    def __new__(cls, value: str):
        sha1_hash = hashlib.sha1(bytes(0)).hexdigest()

        if len(value) != len(sha1_hash):
            raise InvalidPortfolioIDError
        else:
            return super().__new__(cls, value)


class Ticker(str):
    """Represents a stock/security ticker."""
