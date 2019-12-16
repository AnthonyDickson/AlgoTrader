class InsufficientFundsError(Exception):
    """An exception indicated a lack of funds."""
    pass


class InvalidPortfolioIDError(Exception):
    """Error raised  for invalid portfolio IDs."""
