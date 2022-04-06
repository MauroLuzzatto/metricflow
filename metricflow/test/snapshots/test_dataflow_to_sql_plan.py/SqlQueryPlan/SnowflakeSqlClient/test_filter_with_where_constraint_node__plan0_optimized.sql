-- Constrain Output with WHERE
SELECT
  bookings
  , ds
FROM (
  -- Read Elements From Data Source 'bookings_source'
  -- Pass Only Elements:
  --   ['bookings', 'ds']
  SELECT
    1 AS bookings
    , ds
  FROM (
    -- User Defined SQL Query
    SELECT * FROM ***************************.fct_bookings
  ) bookings_source_src_10000
) subq_3
WHERE ds = '2020-01-01'
