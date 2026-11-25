import asyncio
import html
import logging
from . import api, db
from .fmt import match_line


async def _check(bot):
    heroes = await api.hero_names()
    for acc in db.watched_accounts():
        rm = await api.get(f"/players/{acc}/recentMatches", ttl=0)
        if rm:
            latest = rm[0]
            for tg_id, name, last in db.subscribers(acc):
                if latest["match_id"] == last:
                    continue
                db.set_last(tg_id, acc, latest["match_id"])
                if last:  # при первом добавлении не спамим старым матчем
                    text = f"🎮 <b>{html.escape(name)}</b> доиграл катку\n{match_line(latest, heroes)}\n/match {latest['match_id']}"
                    try:
                        await bot.send_message(tg_id, text, parse_mode="HTML")
                    except Exception:
                        logging.exception("send failed")
        await asyncio.sleep(1.2)  # бережём лимиты OpenDota


async def notifier_loop(bot, interval=300):
    db.init()
    while True:
        try:
            await _check(bot)
        except Exception:
            logging.exception("notifier")
        await asyncio.sleep(interval)
