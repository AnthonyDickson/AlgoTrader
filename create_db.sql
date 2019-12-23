BEGIN TRANSACTION;

CREATE TABLE IF NOT EXISTS "portfolio"
(
    "id"         INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT UNIQUE,
    "owner_name" TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS "transactions"
(
    "id"           INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT UNIQUE,
    "portfolio_id" TEXT    NOT NULL,
    "position_id"  INTEGER,
    "type"         INTEGER NOT NULL,
    "quantity"     INTEGER NOT NULL CHECK (quantity >= 0),
    "price"        REAL    NOT NULL CHECK (price >= 0),
    "timestamp"    TEXT    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY ("portfolio_id") REFERENCES "portfolio" ("id") ON UPDATE CASCADE ON DELETE CASCADE,
    FOREIGN KEY ("type") REFERENCES "transaction_type" ("id") ON UPDATE CASCADE ON DELETE RESTRICT,
    FOREIGN KEY ("position_id") REFERENCES "position" ("id") ON UPDATE CASCADE ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS "position"
(
    "id"           INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT UNIQUE,
    "portfolio_id" INTEGER NOT NULL,
    "ticker"       TEXT    NOT NULL,
    FOREIGN KEY ("portfolio_id") REFERENCES "portfolio" ("id") ON DELETE CASCADE ON UPDATE CASCADE
);

CREATE TABLE IF NOT EXISTS "transaction_type"
(
    "id"   INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT UNIQUE,
    "name" TEXT    NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS "historical_marginal_tax_rates"
(
    "tax_year"          TEXT    NOT NULL,
    "bracket_threshold" INTEGER NOT NULL,
    "tax_rate"          REAL    NOT NULL,
    PRIMARY KEY ("tax_year", "bracket_threshold")
);

CREATE TABLE IF NOT EXISTS "historical_capital_gains_tax_rates"
(
    "tax_year"          TEXT    NOT NULL,
    "bracket_threshold" INTEGER NOT NULL,
    "tax_rate"          REAL    NOT NULL,
    PRIMARY KEY ("tax_year", "bracket_threshold")
);

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
    "macd_histogram"    REAL,
    "macd_line"         REAL,
    "signal_line"       REAL,
    PRIMARY KEY ("ticker", "datetime")
);

CREATE TABLE IF NOT EXISTS "portfolio_report"
(
    "id"                           INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT UNIQUE,
    "portfolio_id"                 INTEGER NOT NULL,
    "report_date"                  TEXT    NOT NULL,
    "net_pl"                       REAL    NOT NULL,
    "net_pl_percentage"            REAL    NOT NULL,
    "realised_pl"                  REAL    NOT NULL,
    "realised_pl_percentage"       REAL    NOT NULL,
    "closed_position_value"        REAL    NOT NULL,
    "closed_position_cost"         REAL    NOT NULL,
    "unrealised_pl"                REAL    NOT NULL,
    "unrealised_pl_percentage"     REAL    NOT NULL,
    "open_position_value"          REAL    NOT NULL,
    "open_position_cost"           REAL    NOT NULL,
    "equity"                       REAL    NOT NULL,
    "equity_change"                REAL    NOT NULL,
    "cagr"                         REAL    NOT NULL,
    "accounts_receivable"          REAL    NOT NULL,
    "accounts_receivable_equities" REAL    NOT NULL,
    "available_cash"               REAL    NOT NULL,
    "net_contribution"             REAL    NOT NULL,
    "deposits"                     REAL    NOT NULL,
    "withdrawals"                  REAL    NOT NULL,
    "net_income"                   REAL    NOT NULL,
    "revenue"                      REAL    NOT NULL,
    "revenue_equities"             REAL    NOT NULL,
    "adjustments"                  REAL    NOT NULL,
    "dividends"                    REAL    NOT NULL,
    "cash_settlements"             REAL    NOT NULL,
    "expenses"                     REAL    NOT NULL,
    "taxes"                        REAL    NOT NULL,
    "expenses_equities"            REAL    NOT NULL,
    FOREIGN KEY ("portfolio_id") REFERENCES "portfolio" ("id") ON UPDATE CASCADE ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS "transactions_position_id_type_index" ON "transactions" ("position_id", "type");

CREATE INDEX IF NOT EXISTS "position_portfolio_id_index" ON "position" ("portfolio_id");

CREATE INDEX IF NOT EXISTS "transactions_portfolio_id_index" ON "transactions" ("portfolio_id");

CREATE INDEX IF NOT EXISTS "transactions_portfolio_id_type_index" ON "transactions" ("portfolio_id", "type");

CREATE INDEX IF NOT EXISTS "transactions_position_id_index" ON "transactions" ("position_id");

CREATE INDEX IF NOT EXISTS "daily_stock_data_dividend_amount_index" ON "daily_stock_data" ("dividend_amount" DESC);

CREATE INDEX IF NOT EXISTS "daily_stock_data_datetime_index" ON "daily_stock_data" ("datetime" ASC);

CREATE INDEX IF NOT EXISTS "daily_stock_data_ticker_index" ON "daily_stock_data" ("ticker" ASC);

CREATE INDEX IF NOT EXISTS "historical_marginal_tax_rates_tax_year_bracket_threshold_tax_rate_index"
    ON "historical_marginal_tax_rates" ("tax_year", "bracket_threshold", "tax_rate");

CREATE INDEX IF NOT EXISTS "historical_capital_gains_tax_rates_tax_year_bracket_threshold_tax_rate_index"
    ON "historical_capital_gains_tax_rates" ("tax_year", "bracket_threshold", "tax_rate");

CREATE TRIGGER IF NOT EXISTS transactions_position_id_on_update
    BEFORE UPDATE
    ON transactions
    WHEN (NEW.type IN (3, 4, 5, 6) AND NEW.position_id IS NULL)
BEGIN
    SELECT RAISE(ABORT, 'Transactions dealing with positions must specify a position ID.');
END;

CREATE TRIGGER IF NOT EXISTS transactions_position_id_on_insert
    BEFORE INSERT
    ON transactions
    WHEN (NEW.type IN (3, 4, 5, 6) AND NEW.position_id IS NULL)
BEGIN
    SELECT RAISE(ABORT, 'Transactions dealing with positions must specify a position ID.');
END;

DROP VIEW IF EXISTS portfolio_balance;

CREATE VIEW IF NOT EXISTS portfolio_balance
            (
             portfolio_id,
             balance
                )
AS
SELECT portfolio.id,
       (sums.total_in - sums.total_out)
FROM portfolio
         INNER JOIN (
    SELECT "inner".id as id,
           (SELECT IFNULL(SUM(quantity * price), 0)
            FROM transactions
            WHERE transactions.portfolio_id = "inner".id
              AND transactions.type IN (SELECT transaction_type.id
                                        FROM transaction_type
                                        WHERE transaction_type.name NOT IN ('WITHDRAWAL', 'BUY', 'TAX'))
           )          AS total_in,
           (SELECT IFNULL(SUM(quantity * price), 0)
            FROM transactions
            WHERE transactions.portfolio_id = "inner".id
              AND transactions.type IN (SELECT transaction_type.id
                                        FROM transaction_type
                                        WHERE transaction_type.name IN ('WITHDRAWAL', 'BUY', 'TAX'))
           )          AS total_out
    FROM portfolio AS "inner"
) sums
                    ON sums.id = portfolio.id;

INSERT OR
REPLACE
INTO "transaction_type" ("id", "name")
VALUES (1, 'DEPOSIT'),
       (2, 'WITHDRAWAL'),
       (3, 'BUY'),
       (4, 'SELL'),
       (5, 'DIVIDEND'),
       (6, 'CASH_SETTLEMENT'),
       (7, 'TAX');

INSERT OR
REPLACE
INTO "historical_marginal_tax_rates" (tax_year, bracket_threshold, tax_rate)
VALUES ('2000-01-01 00:00:00', 0, 0.15),
       ('2000-01-01 00:00:00', 26250, 0.28),
       ('2000-01-01 00:00:00', 63550, 0.31),
       ('2000-01-01 00:00:00', 132600, 0.36),
       ('2000-01-01 00:00:00', 288350, 0.396),
       ('2001-01-01 00:00:00', 0, 0.15),
       ('2001-01-01 00:00:00', 27050, 0.275),
       ('2001-01-01 00:00:00', 65550, 0.305),
       ('2001-01-01 00:00:00', 136750, 0.355),
       ('2001-01-01 00:00:00', 297350, 0.391),
       ('2002-01-01 00:00:00', 0, 0.10),
       ('2002-01-01 00:00:00', 6000, 0.15),
       ('2002-01-01 00:00:00', 27950, 0.27),
       ('2002-01-01 00:00:00', 67700, 0.30),
       ('2002-01-01 00:00:00', 141250, 0.35),
       ('2002-01-01 00:00:00', 307050, 0.386),
       ('2003-01-01 00:00:00', 0, 0.10),
       ('2003-01-01 00:00:00', 7000, 0.15),
       ('2003-01-01 00:00:00', 28400, 0.25),
       ('2003-01-01 00:00:00', 68800, 0.28),
       ('2003-01-01 00:00:00', 143500, 0.33),
       ('2003-01-01 00:00:00', 311950, 0.35),
       ('2004-01-01 00:00:00', 0, 0.10),
       ('2004-01-01 00:00:00', 7150, 0.15),
       ('2004-01-01 00:00:00', 29050, 0.25),
       ('2004-01-01 00:00:00', 70350, 0.28),
       ('2004-01-01 00:00:00', 146750, 0.33),
       ('2004-01-01 00:00:00', 319100, 0.35),
       ('2005-01-01 00:00:00', 0, 0.10),
       ('2005-01-01 00:00:00', 7300, 0.15),
       ('2005-01-01 00:00:00', 29700, 0.25),
       ('2005-01-01 00:00:00', 71950, 0.28),
       ('2005-01-01 00:00:00', 150150, 0.33),
       ('2005-01-01 00:00:00', 326450, 0.35),
       ('2006-01-01 00:00:00', 0, 0.10),
       ('2006-01-01 00:00:00', 7550, 0.15),
       ('2006-01-01 00:00:00', 30650, 0.25),
       ('2006-01-01 00:00:00', 74200, 0.28),
       ('2006-01-01 00:00:00', 154800, 0.33),
       ('2006-01-01 00:00:00', 336550, 0.35),
       ('2007-01-01 00:00:00', 0, 0.10),
       ('2007-01-01 00:00:00', 7825, 0.15),
       ('2007-01-01 00:00:00', 31850, 0.25),
       ('2007-01-01 00:00:00', 77100, 0.28),
       ('2007-01-01 00:00:00', 160850, 0.33),
       ('2007-01-01 00:00:00', 349700, 0.35),
       ('2008-01-01 00:00:00', 0, 0.10),
       ('2008-01-01 00:00:00', 8025, 0.15),
       ('2008-01-01 00:00:00', 32550, 0.25),
       ('2008-01-01 00:00:00', 78850, 0.28),
       ('2008-01-01 00:00:00', 164550, 0.33),
       ('2008-01-01 00:00:00', 357700, 0.35),
       ('2009-01-01 00:00:00', 0, 0.10),
       ('2009-01-01 00:00:00', 8350, 0.15),
       ('2009-01-01 00:00:00', 33950, 0.25),
       ('2009-01-01 00:00:00', 82250, 0.28),
       ('2009-01-01 00:00:00', 171550, 0.33),
       ('2009-01-01 00:00:00', 372950, 0.35),
       ('2010-01-01 00:00:00', 0, 0.10),
       ('2010-01-01 00:00:00', 8375, 0.15),
       ('2010-01-01 00:00:00', 34000, 0.25),
       ('2010-01-01 00:00:00', 82400, 0.28),
       ('2010-01-01 00:00:00', 171850, 0.33),
       ('2010-01-01 00:00:00', 373650, 0.35),
       ('2011-01-01 00:00:00', 0, 0.10),
       ('2011-01-01 00:00:00', 8500, 0.15),
       ('2011-01-01 00:00:00', 34500, 0.25),
       ('2011-01-01 00:00:00', 83600, 0.28),
       ('2011-01-01 00:00:00', 174400, 0.33),
       ('2011-01-01 00:00:00', 379150, 0.35),
       ('2012-01-01 00:00:00', 0, 0.10),
       ('2012-01-01 00:00:00', 8700, 0.15),
       ('2012-01-01 00:00:00', 35350, 0.25),
       ('2012-01-01 00:00:00', 85650, 0.28),
       ('2012-01-01 00:00:00', 178650, 0.33),
       ('2012-01-01 00:00:00', 388350, 0.35),
       ('2013-01-01 00:00:00', 0, 0.10),
       ('2013-01-01 00:00:00', 8925, 0.15),
       ('2013-01-01 00:00:00', 36250, 0.25),
       ('2013-01-01 00:00:00', 87850, 0.28),
       ('2013-01-01 00:00:00', 183250, 0.33),
       ('2013-01-01 00:00:00', 398350, 0.35),
       ('2013-01-01 00:00:00', 400000, 0.396),
       ('2014-01-01 00:00:00', 0, 0.10),
       ('2014-01-01 00:00:00', 9075, 0.15),
       ('2014-01-01 00:00:00', 36900, 0.25),
       ('2014-01-01 00:00:00', 89350, 0.28),
       ('2014-01-01 00:00:00', 186350, 0.33),
       ('2014-01-01 00:00:00', 405100, 0.35),
       ('2014-01-01 00:00:00', 406750, 0.396),
       ('2015-01-01 00:00:00', 0, 0.10),
       ('2015-01-01 00:00:00', 9225, 0.15),
       ('2015-01-01 00:00:00', 37450, 0.25),
       ('2015-01-01 00:00:00', 90750, 0.28),
       ('2015-01-01 00:00:00', 189300, 0.33),
       ('2015-01-01 00:00:00', 411500, 0.35),
       ('2015-01-01 00:00:00', 413200, 0.396),
       ('2016-01-01 00:00:00', 0, 0.10),
       ('2016-01-01 00:00:00', 9275, 0.15),
       ('2016-01-01 00:00:00', 37650, 0.25),
       ('2016-01-01 00:00:00', 91150, 0.28),
       ('2016-01-01 00:00:00', 190151, 0.33),
       ('2016-01-01 00:00:00', 413350, 0.35),
       ('2016-01-01 00:00:00', 415050, 0.396),
       ('2017-01-01 00:00:00', 0, 0.10),
       ('2017-01-01 00:00:00', 9325, 0.15),
       ('2017-01-01 00:00:00', 37950, 0.25),
       ('2017-01-01 00:00:00', 91900, 0.28),
       ('2017-01-01 00:00:00', 191650, 0.33),
       ('2017-01-01 00:00:00', 416700, 0.35),
       ('2017-01-01 00:00:00', 418400, 0.396),
       ('2018-01-01 00:00:00', 0, 0.10),
       ('2018-01-01 00:00:00', 9525, 0.12),
       ('2018-01-01 00:00:00', 38700, 0.22),
       ('2018-01-01 00:00:00', 82500, 0.24),
       ('2018-01-01 00:00:00', 157500, 0.32),
       ('2018-01-01 00:00:00', 200000, 0.35),
       ('2018-01-01 00:00:00', 500000, 0.37),
       ('2019-01-01 00:00:00', 0, 0.10),
       ('2019-01-01 00:00:00', 9700, 0.12),
       ('2019-01-01 00:00:00', 39475, 0.22),
       ('2019-01-01 00:00:00', 84200, 0.24),
       ('2019-01-01 00:00:00', 160725, 0.32),
       ('2019-01-01 00:00:00', 204100, 0.35),
       ('2019-01-01 00:00:00', 510300, 0.37);

INSERT OR
REPLACE
INTO "historical_capital_gains_tax_rates" (tax_year, bracket_threshold, tax_rate)
VALUES ('2000-01-01 00:00:00', 0, 0.10),
       ('2000-01-01 00:00:00', 26250, 0.20),
       ('2001-01-01 00:00:00', 0, 0.10),
       ('2001-01-01 00:00:00', 27050, 0.20),
       ('2002-01-01 00:00:00', 0, 0.10),
       ('2002-01-01 00:00:00', 27950, 0.20),
       ('2003-01-01 00:00:00', 0, 0.10),
       ('2003-01-01 00:00:00', 7000, 0.10),
       ('2003-01-01 00:00:00', 28400, 0.15),
       ('2004-01-01 00:00:00', 0, 0.10),
       ('2004-01-01 00:00:00', 29050, 0.15),
       ('2005-01-01 00:00:00', 0, 0.10),
       ('2005-01-01 00:00:00', 29700, 0.15),
       ('2006-01-01 00:00:00', 0, 0.10),
       ('2006-01-01 00:00:00', 30650, 0.15),
       ('2007-01-01 00:00:00', 0, 0.10),
       ('2007-01-01 00:00:00', 31850, 0.15),
       ('2008-01-01 00:00:00', 0, 0.00),
       ('2008-01-01 00:00:00', 32550, 0.15),
       ('2009-01-01 00:00:00', 0, 0.00),
       ('2009-01-01 00:00:00', 33950, 0.15),
       ('2010-01-01 00:00:00', 0, 0.00),
       ('2010-01-01 00:00:00', 34000, 0.15),
       ('2011-01-01 00:00:00', 0, 0.00),
       ('2011-01-01 00:00:00', 34500, 0.15),
       ('2012-01-01 00:00:00', 0, 0.00),
       ('2012-01-01 00:00:00', 35350, 0.15),
       ('2013-01-01 00:00:00', 0, 0.0),
       ('2013-01-01 00:00:00', 36250, 0.15),
       ('2013-01-01 00:00:00', 400000, 0.20),
       ('2014-01-01 00:00:00', 0, 0.10),
       ('2014-01-01 00:00:00', 36900, 0.15),
       ('2014-01-01 00:00:00', 406750, 0.20),
       ('2015-01-01 00:00:00', 0, 0.10),
       ('2015-01-01 00:00:00', 37450, 0.15),
       ('2015-01-01 00:00:00', 413200, 0.20),
       ('2016-01-01 00:00:00', 0, 0.10),
       ('2016-01-01 00:00:00', 37650, 0.15),
       ('2016-01-01 00:00:00', 415050, 0.20),
       ('2017-01-01 00:00:00', 0, 0.10),
       ('2017-01-01 00:00:00', 37950, 0.15),
       ('2017-01-01 00:00:00', 418400, 0.20),
       ('2018-01-01 00:00:00', 0, 0.00),
       ('2018-01-01 00:00:00', 38600, 0.15),
       ('2018-01-01 00:00:00', 425800, 0.20),
       ('2019-01-01 00:00:00', 0, 0.00),
       ('2019-01-01 00:00:00', 39375, 0.15),
       ('2019-01-01 00:00:00', 434550, 0.20);
COMMIT;
