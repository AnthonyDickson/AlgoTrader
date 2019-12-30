PRAGMA FOREIGN_KEYS= ON;
DELETE
FROM portfolio;
UPDATE sqlite_sequence
SET seq=0;
VACUUM;
