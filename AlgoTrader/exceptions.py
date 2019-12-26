class InsufficientFundsError(Exception):
    """An exception indicated a lack of funds."""
    pass


class InvalidPortfolioIDError(Exception):
    """Error raised  for invalid portfolio IDs."""


class ConfigParseError(Exception):
    """Error raised when a config file cannot be parsed."""


class InvalidFrequencyFormatError(ConfigParseError):
    """Error raised when an invalid frequency format is encountered."""
