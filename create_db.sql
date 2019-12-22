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

CREATE INDEX IF NOT EXISTS "transactions_position_id_type_index" ON "transactions" (
                                                                                    "position_id",
                                                                                    "type"
    );

CREATE INDEX IF NOT EXISTS "position_portfolio_id_index" ON "position" (
                                                                        "portfolio_id"
    );

CREATE INDEX IF NOT EXISTS "transactions_portfolio_id_index" ON "transactions" (
                                                                                "portfolio_id"
    );

CREATE INDEX IF NOT EXISTS "transactions_portfolio_id_type_index" ON "transactions" (
                                                                                     "portfolio_id",
                                                                                     "type"
    );

CREATE INDEX IF NOT EXISTS "transactions_position_id_index" ON "transactions" (
                                                                               "position_id"
    );

CREATE INDEX IF NOT EXISTS "daily_stock_data_dividend_amount_index" ON "daily_stock_data" (
                                                                                           "dividend_amount" DESC
    );

CREATE INDEX IF NOT EXISTS "daily_stock_data_datetime_index" ON "daily_stock_data" (
                                                                                    "datetime" ASC
    );

CREATE INDEX IF NOT EXISTS "daily_stock_data_ticker_index" ON "daily_stock_data" (
                                                                                  "ticker" ASC
    );

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
CREATE VIEW IF NOT EXISTS position_totals_by_type
            (
             position_id,
             type,
             total
                )
AS
SELECT position_id,
       type,
       SUM(quantity * price)
FROM transactions
GROUP BY position_id, type;
CREATE VIEW IF NOT EXISTS portfolio_summary
            (
             portfolio_id,
             timestamp,
             total_in,
             total_out,
             balance,
             num_open_positions,
             num_closed_positions,
             num_all_positions,
             total_dividends,
             total_cash_settlements,
             total_adjustments
                )
AS
SELECT portfolio.id,
       CURRENT_TIMESTAMP,
       (sums.total_in + sums.total_dividends + sums.total_cash_settlements),
       (sums.total_out),
       (sums.total_in + sums.total_dividends + sums.total_cash_settlements - sums.total_out),
       (
           SELECT IFNULL(COUNT(position_id), 0)
           FROM open_positions
           WHERE open_positions.portfolio_id = portfolio.id
       ),
       (
           SELECT IFNULL(COUNT(position_id), 0)
           FROM closed_positions
           WHERE closed_positions.portfolio_id = portfolio.id
       ),
       (
           SELECT (
                      SELECT IFNULL(COUNT(open_positions.position_id), 0)
                      FROM open_positions
                  ) + (
                      SELECT IFNULL(COUNT(closed_positions.position_id), 0)
                      FROM closed_positions
                  )
       ),
       (sums.total_dividends),
       (sums.total_cash_settlements),
       (sums.total_dividends + sums.total_cash_settlements)
FROM portfolio
         INNER JOIN (
    SELECT "inner".id as id,
           (SELECT IFNULL(SUM(quantity * price), 0)
            FROM transactions
            WHERE transactions.portfolio_id = "inner".id
              AND transactions.type IN (SELECT transaction_type.id
                                        FROM transaction_type
                                        WHERE transaction_type.name NOT IN ('WITHDRAWAL', 'BUY'))
           )          AS total_in,
           (SELECT IFNULL(SUM(quantity * price), 0)
            FROM transactions
            WHERE transactions.portfolio_id = "inner".id
              AND transactions.type IN (SELECT transaction_type.id
                                        FROM transaction_type
                                        WHERE transaction_type.name IN ('WITHDRAWAL', 'BUY'))
           )          AS total_out,
           (SELECT IFNULL(SUM(quantity * price), 0)
            FROM transactions
            WHERE transactions.portfolio_id = "inner".id
              AND transactions.type = (SELECT transaction_type.id
                                       FROM transaction_type
                                       WHERE transaction_type.name = 'DIVIDEND')
           )          AS total_dividends,
           (SELECT IFNULL(SUM(quantity * price), 0)
            FROM transactions
            WHERE transactions.portfolio_id = "inner".id
              AND transactions.type = (SELECT transaction_type.id
                                       FROM transaction_type
                                       WHERE transaction_type.name = 'CASH_SETTLEMENT')
           )          AS total_cash_settlements
    FROM portfolio AS "inner"
) sums
                    ON sums.id = portfolio.id;

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
                                        WHERE transaction_type.name NOT IN ('WITHDRAWAL', 'BUY'))
           )          AS total_in,
           (SELECT IFNULL(SUM(quantity * price), 0)
            FROM transactions
            WHERE transactions.portfolio_id = "inner".id
              AND transactions.type IN (SELECT transaction_type.id
                                        FROM transaction_type
                                        WHERE transaction_type.name IN ('WITHDRAWAL', 'BUY'))
           )          AS total_out
    FROM portfolio AS "inner"
) sums
                    ON sums.id = portfolio.id;

CREATE VIEW IF NOT EXISTS position_summary
            (
             position_id,
             portfolio_id,
             ticker,
             open_date,
             close_date,
             is_closed,
             quantity,
             entry_price,
             entry_value,
             exit_price,
             exit_value,
             total_dividends,
             total_cash_settlements,
             total_adjustments,
             realised_pl,
             realised_pl_percentage
                )
AS
SELECT position.id,
       position.portfolio_id,
       position.ticker,
       (
           SELECT timestamp
           FROM transactions
           WHERE position_id = position.id
             AND type = (
               SELECT transaction_type.id
               FROM transaction_type
               WHERE transaction_type.name = 'BUY'
           )
       ),
       (
           SELECT timestamp
           FROM transactions
           WHERE position_id = position.id
             AND type = (
               SELECT transaction_type.id
               FROM transaction_type
               WHERE transaction_type.name = 'SELL'
           )
       ),
       (
           SELECT CASE
                      WHEN EXISTS
                          (
                              SELECT transactions.id
                              FROM transactions
                              WHERE position_id = position.id
                                AND transactions.type = (
                                  SELECT transaction_type.id
                                  FROM transaction_type
                                  WHERE transaction_type.name = 'SELL'
                              )
                          ) THEN 1
                      ELSE 0
                      END is_closed
       ),
       (
           SELECT transactions.quantity
           FROM transactions
           WHERE transactions.position_id = position.id
             AND transactions.type = (
               SELECT transaction_type.id
               FROM transaction_type
               WHERE transaction_type.name = 'BUY'
           )
       ),
       (
           SELECT transactions.price
           FROM transactions
           WHERE transactions.position_id = position.id
             AND transactions.type = (
               SELECT transaction_type.id
               FROM transaction_type
               WHERE transaction_type.name = 'BUY'
           )
       ),
       (sums.entry_value),
       (
           SELECT transactions.price
           FROM transactions
           WHERE transactions.position_id = position.id
             AND transactions.type = (
               SELECT transaction_type.id
               FROM transaction_type
               WHERE transaction_type.name = 'SELL'
           )
       ),
       (sums.exit_value),
       (sums.total_dividends),
       (sums.total_cash_settlements),
       (sums.total_dividends + sums.total_cash_settlements),
       (sums.total_dividends + sums.total_cash_settlements + IFNULL(sums.exit_value - sums.entry_value, 0)),
       ((sums.total_dividends + sums.total_cash_settlements + IFNULL(sums.exit_value - sums.entry_value, 0)) /
        sums.entry_value * 100)
FROM position
         INNER JOIN position_totals AS sums
                    ON sums.position_id = position.id;

CREATE VIEW IF NOT EXISTS position_totals
            (
             position_id,
             entry_value,
             exit_value,
             total_dividends,
             total_cash_settlements
                )
AS
SELECT a.position_id,
       IFNULL(a.total, 0) as entry_value,
       IFNULL(b.total, 0) as exit_value,
       IFNULL(c.total, 0) as total_dividends,
       IFNULL(d.total, 0) as total_cash_settlements
FROM position_totals_by_type a
         LEFT JOIN (
    SELECT position_id, total
    FROM position_totals_by_type
    WHERE type = (
        SELECT transaction_type.id
        FROM transaction_type
        WHERE transaction_type.name = 'BUY'
    )
) AS b ON a.position_id = b.position_id
         LEFT JOIN (
    SELECT position_id, total
    FROM position_totals_by_type
    WHERE type = (
        SELECT transaction_type.id
        FROM transaction_type
        WHERE transaction_type.name = 'DIVIDEND'
    )
) AS c ON a.position_id = c.position_id
         LEFT JOIN (
    SELECT position_id, total
    FROM position_totals_by_type
    WHERE type = (
        SELECT transaction_type.id
        FROM transaction_type
        WHERE transaction_type.name = 'CASH_SETTLEMENT'
    )
) AS d ON a.position_id = d.position_id
WHERE type = (
    SELECT transaction_type.id
    FROM transaction_type
    WHERE transaction_type.name = 'BUY'
);

CREATE VIEW IF NOT EXISTS closed_positions
            (
             portfolio_id,
             position_id
                )
AS
SELECT portfolio_id, id AS position_id
FROM position
WHERE EXISTS(
              SELECT transactions.id
              FROM transactions
              WHERE position_id = position.id
                AND transactions.type = (
                  SELECT DISTINCT id
                  FROM transaction_type
                  WHERE transaction_type.name = 'SELL'
              )
          );

CREATE VIEW IF NOT EXISTS open_positions
            (
             portfolio_id,
             position_id
                )
AS
SELECT portfolio_id, id AS position_id
FROM position
WHERE NOT EXISTS(
        SELECT transactions.id
        FROM transactions
        WHERE position_id = position.id
          AND transactions.type = (
            SELECT DISTINCT id
            FROM transaction_type
            WHERE transaction_type.name = 'SELL'
        )
    );

INSERT OR
REPLACE
INTO "transaction_type" ("id", "name")
VALUES (1, 'DEPOSIT'),
       (2, 'WITHDRAWAL'),
       (3, 'BUY'),
       (4, 'SELL'),
       (5, 'DIVIDEND'),
       (6, 'CASH_SETTLEMENT');
COMMIT;
