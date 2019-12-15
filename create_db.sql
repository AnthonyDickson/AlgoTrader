BEGIN TRANSACTION;
CREATE TABLE IF NOT EXISTS "daily_stock_data"
(
    "ticker"            TEXT    NOT NULL,
    "datetime"          TEXT    NOT NULL,
    "open"              REAL    NOT NULL,
    "close"             REAL    NOT NULL,
    "adjusted_close"    REAL    NOT NULL,
    "low"               REAL    NOT NULL,
    "high"              REAL    NOT NULL,
    "volume"            INTEGER NOT NULL,
    "dividend_amount"   REAL    NOT NULL,
    "split_coefficient" REAL    NOT NULL,
    "macd_histogram"    REAL    NOT NULL,
    "macd_line"         REAL    NOT NULL,
    "signal_line"       REAL    NOT NULL,
    PRIMARY KEY ("ticker", "datetime")
);
CREATE INDEX IF NOT EXISTS "daily_stock_data_ticker_index" ON "daily_stock_data" (
                                                                                  "ticker" ASC
    );
CREATE INDEX IF NOT EXISTS "daily_stock_data_datetime_index" ON "daily_stock_data" (
                                                                                    "datetime" ASC
    );
CREATE TABLE IF NOT EXISTS "portfolio"
(
    "id"              INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT UNIQUE,
    "balance"         REAL    NOT NULL,
    "initial_balance" REAL    NOT NULL
);
CREATE TABLE IF NOT EXISTS "position"
(
    "id"           INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT UNIQUE,
    "portfolio_id" INTEGER NOT NULL,
    "ticker"       TEXT    NOT NULL CHECK (LENGTH(ticker) <= 5),
    "date"         INTEGER NOT NULL CHECK (date > 0),
    "entry_price"  REAL    NOT NULL CHECK (entry_price >= 0),
    "quantity"     INTEGER NOT NULL CHECK (quantity > 0),
    "exit_price"   REAL DEFAULT 0 NOT NULL CHECK (exit_price >= 0),
    "is_closed"    INTEGER NOT NULL CHECK (is_closed = 0 OR is_closed = 1),
    FOREIGN KEY ("portfolio_id") REFERENCES "portfolio" ("id") ON DELETE CASCADE ON UPDATE CASCADE
);
COMMIT;
