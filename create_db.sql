BEGIN TRANSACTION;
DROP TABLE IF EXISTS "position";
CREATE TABLE IF NOT EXISTS "position"
(
    "id"           INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT UNIQUE,
    "portfolio_id" INTEGER NOT NULL,
    "ticker"       TEXT    NOT NULL CHECK (LENGTH(ticker) <= 4),
    "date"         INTEGER NOT NULL CHECK (date > 0),
    "entry_price"  REAL    NOT NULL CHECK (entry_price > 0),
    "quantity"     INTEGER NOT NULL CHECK (quantity > 0),
    "exit_price"   REAL CHECK (exit_price > 0),
    "is_closed"    INTEGER NOT NULL CHECK (is_closed = 0 OR is_closed = 1),
    FOREIGN KEY ("portfolio_id") REFERENCES "portfolio" ("id") ON DELETE CASCADE ON UPDATE CASCADE
);
DROP TABLE IF EXISTS "stock_data";
CREATE TABLE IF NOT EXISTS "stock_data"
(
    "id"             INTEGER PRIMARY KEY AUTOINCREMENT,
    "ticker"         TEXT    NOT NULL,
    "date"           INTEGER NOT NULL,
    "close_price"    REAL    NOT NULL,
    "macd_histogram" REAL    NOT NULL,
    "macd_line"      REAL    NOT NULL,
    "signal_line"    REAL    NOT NULL
);
DROP TABLE IF EXISTS "portfolio";
CREATE TABLE IF NOT EXISTS "portfolio"
(
    "id"              INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT UNIQUE,
    "balance"         REAL    NOT NULL,
    "initial_balance" REAL    NOT NULL
);
COMMIT;
