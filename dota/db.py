import os
import asyncpg

_pool = None


async def init():
    global _pool
    if _pool:
        return
    _pool = await asyncpg.create_pool(
        os.environ["DATABASE_URL"], min_size=1, max_size=5,
        statement_cache_size=0, max_inactive_connection_lifetime=60)
    await _pool.execute("""
    CREATE TABLE IF NOT EXISTS users(tg_id BIGINT PRIMARY KEY, account_id BIGINT);
    CREATE TABLE IF NOT EXISTS watch(
        tg_id BIGINT, account_id BIGINT, name TEXT, last_match BIGINT DEFAULT 0,
        PRIMARY KEY(tg_id, account_id));
    CREATE TABLE IF NOT EXISTS scores(tg_id BIGINT PRIMARY KEY, name TEXT, points INT DEFAULT 0);
    """)


async def set_account(tg_id, acc):
    await _pool.execute(
        "INSERT INTO users VALUES($1,$2) ON CONFLICT (tg_id) DO UPDATE SET account_id=EXCLUDED.account_id",
        tg_id, acc)


async def get_account(tg_id):
    return await _pool.fetchval("SELECT account_id FROM users WHERE tg_id=$1", tg_id)


async def watch(tg_id, acc, name, last):
    await _pool.execute(
        "INSERT INTO watch VALUES($1,$2,$3,$4) ON CONFLICT (tg_id, account_id) "
        "DO UPDATE SET name=EXCLUDED.name, last_match=EXCLUDED.last_match", tg_id, acc, name, last)


async def unwatch(tg_id, acc):
    await _pool.execute("DELETE FROM watch WHERE tg_id=$1 AND account_id=$2", tg_id, acc)


async def my_watch(tg_id):
    return await _pool.fetch("SELECT account_id, name FROM watch WHERE tg_id=$1", tg_id)


async def watched_accounts():
    return [r[0] for r in await _pool.fetch("SELECT DISTINCT account_id FROM watch")]


async def subscribers(acc):
    return await _pool.fetch("SELECT tg_id, name, last_match FROM watch WHERE account_id=$1", acc)


async def set_last(tg_id, acc, match_id):
    await _pool.execute("UPDATE watch SET last_match=$1 WHERE tg_id=$2 AND account_id=$3", match_id, tg_id, acc)


async def add_point(tg_id, name):
    await _pool.execute(
        "INSERT INTO scores VALUES($1,$2,1) ON CONFLICT (tg_id) "
        "DO UPDATE SET points=scores.points+1, name=EXCLUDED.name", tg_id, name)


async def top(n=10):
    return await _pool.fetch("SELECT name, points FROM scores ORDER BY points DESC LIMIT $1", n)
