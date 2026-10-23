# Fabric notebook: load the Northbridge League dataset into Lakehouse tables.
#
# Paste into a new notebook attached to the `pitchside` lakehouse (docs/FABRIC.md, step 3),
# or import this file (Workspace > Import > Notebook). Run all cells. About two minutes.
#
# Reads the Parquet export of 200 synthetic matches (`scripts/export_dataset.py`) and
# data/league/clubs.json from Files/northbridge/, and writes Delta tables the Power BI report
# reads with Direct Lake: clubs, players, matches, events, team_match and league_table.
# Every club, player and match is invented (docs/03). The SQL below is plain enough to run on
# SQLite too, which is how backend/tests/test_fabric.py checks it. `spark` and `display` are
# notebook globals, so this file is left out of ruff and mypy.

# %%
from pyspark.sql import functions as F

BASE = "Files/northbridge"

TEAM_MATCH_SQL = """
WITH sides AS (
    SELECT match_id, matchday, home AS team, away AS opponent, 1 AS is_home,
           home_goals AS goals_for, away_goals AS goals_against
    FROM matches
    UNION ALL
    SELECT match_id, matchday, away AS team, home AS opponent, 0 AS is_home,
           away_goals AS goals_for, home_goals AS goals_against
    FROM matches
),
ev AS (
    SELECT match_id, team,
           SUM(CASE WHEN type = 'shot' THEN 1 ELSE 0 END) AS shots,
           SUM(CASE WHEN type = 'shot' AND outcome IN ('goal', 'saved') THEN 1 ELSE 0 END)
               AS shots_on_target,
           ROUND(SUM(CASE WHEN type = 'shot' THEN COALESCE(xg, 0) ELSE 0 END), 2) AS xg,
           SUM(CASE WHEN type = 'pass' THEN 1 ELSE 0 END) AS passes,
           SUM(CASE WHEN type = 'pass' AND outcome = 'complete' THEN 1 ELSE 0 END)
               AS passes_complete,
           ROUND(AVG(CASE WHEN type = 'pass' THEN pass_difficulty END), 1) AS avg_pass_difficulty,
           SUM(CASE WHEN type = 'pass' AND outcome = 'complete' AND pass_difficulty >= 70
                    THEN 1 ELSE 0 END) AS hard_passes_complete,
           SUM(CASE WHEN type IN ('tackle', 'interception') THEN 1 ELSE 0 END) AS ball_wins,
           SUM(CASE WHEN type = 'foul' THEN 1 ELSE 0 END) AS fouls,
           SUM(CASE WHEN type = 'card' AND outcome = 'yellow' THEN 1 ELSE 0 END) AS yellows,
           SUM(CASE WHEN type = 'card' AND outcome = 'red' THEN 1 ELSE 0 END) AS reds,
           SUM(CASE WHEN type = 'corner' THEN 1 ELSE 0 END) AS corners
    FROM events
    WHERE team IS NOT NULL AND team <> ''
    GROUP BY match_id, team
)
SELECT s.match_id, s.matchday, s.team, s.opponent, s.is_home, s.goals_for, s.goals_against,
       CASE WHEN s.goals_for > s.goals_against THEN 'W'
            WHEN s.goals_for = s.goals_against THEN 'D' ELSE 'L' END AS result,
       CASE WHEN s.goals_for > s.goals_against THEN 3
            WHEN s.goals_for = s.goals_against THEN 1 ELSE 0 END AS points,
       COALESCE(e.shots, 0) AS shots,
       COALESCE(e.shots_on_target, 0) AS shots_on_target,
       COALESCE(e.xg, 0) AS xg,
       COALESCE(e.passes, 0) AS passes,
       COALESCE(e.passes_complete, 0) AS passes_complete,
       ROUND(100.0 * COALESCE(e.passes, 0)
             / SUM(COALESCE(e.passes, 0)) OVER (PARTITION BY s.match_id), 1) AS pass_share_pct,
       e.avg_pass_difficulty,
       COALESCE(e.hard_passes_complete, 0) AS hard_passes_complete,
       COALESCE(e.ball_wins, 0) AS ball_wins,
       COALESCE(e.fouls, 0) AS fouls,
       COALESCE(e.yellows, 0) AS yellows,
       COALESCE(e.reds, 0) AS reds,
       COALESCE(e.corners, 0) AS corners
FROM sides s
LEFT JOIN ev e ON e.match_id = s.match_id AND e.team = s.team
"""

LEAGUE_TABLE_SQL = """
SELECT team,
       COUNT(*) AS played,
       SUM(CASE WHEN result = 'W' THEN 1 ELSE 0 END) AS won,
       SUM(CASE WHEN result = 'D' THEN 1 ELSE 0 END) AS drawn,
       SUM(CASE WHEN result = 'L' THEN 1 ELSE 0 END) AS lost,
       SUM(goals_for) AS goals_for,
       SUM(goals_against) AS goals_against,
       SUM(goals_for) - SUM(goals_against) AS goal_difference,
       SUM(points) AS points,
       ROUND(SUM(xg), 1) AS xg_for
FROM team_match
GROUP BY team
"""

# %%
# The raw files, as exported.
matches = spark.read.parquet(f"{BASE}/matches.parquet")
events = spark.read.parquet(f"{BASE}/events.parquet")
players = spark.read.parquet(f"{BASE}/players.parquet")
clubs = (
    spark.read.option("multiLine", True)
    .json(f"{BASE}/clubs.json")
    .select(F.explode("clubs").alias("c"))
    .select(
        F.col("c.code").alias("team"),
        F.col("c.name").alias("club"),
        F.col("c.ground").alias("ground"),
        F.col("c.manager").alias("manager"),
        F.col("c.identity.label").alias("style"),
        F.col("c.identity.formation").alias("formation"),
        F.col("c.primary_color").alias("colour"),
    )
)
events = events.withColumn("minute", F.floor(F.col("t_match") / 60).cast("int"))

for name, df in [("clubs", clubs), ("players", players), ("matches", matches), ("events", events)]:
    df.write.mode("overwrite").option("overwriteSchema", "true").format("delta").saveAsTable(name)
    print(f"{name}: {df.count():,} rows")

# %%
# Per side per match, then the league table, from the tables above.
team_match = spark.sql(TEAM_MATCH_SQL)
team_match.write.mode("overwrite").option("overwriteSchema", "true").format("delta").saveAsTable(
    "team_match"
)
league_table = spark.sql(LEAGUE_TABLE_SQL)
league_table.write.mode("overwrite").option("overwriteSchema", "true").format(
    "delta"
).saveAsTable("league_table")
display(league_table.orderBy(F.desc("points"), F.desc("goal_difference")))
