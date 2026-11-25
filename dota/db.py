import os
import sqlite3

# На Render без Persistent Disk файл стирается при каждом деплое.
# Смонтируй диск и задай DB_PATH=/data/bot.db (позже можно перейти на Postgres).
PATH = os.getenv("DB_PATH", "dota.db")


def _c():
    return sqlite3.connect(PATH)


def init():
    with _c() as c:
        c.executescript("""
        CREATE TABLE IF NOT EXISTS users(tg_id INTEGER PRIMARY KEY, account_id INTEGER);
        CREATE TABLE IF NOT EXISTS watch(
            tg_id INTEGER, account_id INTEGER, name TEXT, last_match INTEGER DEFAULT 0,
            PRIMARY KEY(tg_id, account_id));
        CREATE TABLE IF NOT EXISTS scores(tg_id INTEGER PRIMARY KEY, name TEXT, points INTEGER DEFAULT 0);
        """)


def set_account(tg_id, acc):
    with _c() as c:
        c.execute("INSERT OR REPLACE INTO users VALUES(?,?)", (tg_id, acc))


def get_account(tg_id):
    with _c() as c:
        r = c.execute("SELECT account_id FROM users WHERE tg_id=?", (tg_id,)).fetchone()
    return r[0] if r else None


def watch(tg_id, acc, name, last):
    with _c() as c:
        c.execute("INSERT OR REPLACE INTO watch VALUES(?,?,?,?)", (tg_id, acc, name, last))


def unwatch(tg_id, acc):
    with _c() as c:
        c.execute("DELETE FROM watch WHERE tg_id=? AND account_id=?", (tg_id, acc))


def my_watch(tg_id):
    with _c() as c:
        return c.execute("SELECT account_id, name FROM watch WHERE tg_id=?", (tg_id,)).fetchall()


def watched_accounts():
    with _c() as c:
        return [r[0] for r in c.execute("SELECT DISTINCT account_id FROM watch")]


def subscribers(acc):
    with _c() as c:
        return c.execute("SELECT tg_id, name, last_match FROM watch WHERE account_id=?", (acc,)).fetchall()


def set_last(tg_id, acc, match_id):
    with _c() as c:
        c.execute("UPDATE watch SET last_match=? WHERE tg_id=? AND account_id=?", (match_id, tg_id, acc))


def add_point(tg_id, name):
    with _c() as c:
        c.execute("INSERT OR IGNORE INTO scores(tg_id, name, points) VALUES(?,?,0)", (tg_id, name))
        c.execute("UPDATE scores SET points=points+1, name=? WHERE tg_id=?", (name, tg_id))


def top(n=10):
    with _c() as c:
        return c.execute("SELECT name, points FROM scores ORDER BY points DESC LIMIT ?", (n,)).fetchall()
