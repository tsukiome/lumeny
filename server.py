import asyncio
from pathlib import Path
from aiohttp import web
from dota import api
from dota.fmt import rank, is_win

WEB = Path(__file__).parent / "webapp"


async def health(request):
    return web.Response(text="ok")


async def index(request):
    f = WEB / "index.html"
    if not f.exists():
        return web.Response(status=404, text="Не найден файл webapp/index.html в репозитории")
    return web.Response(text=f.read_text(encoding="utf-8"),
                        content_type="text/html", charset="utf-8")


async def profile(request):
    acc = api.to_account_id(request.match_info["acc"])
    if not acc:
        return web.json_response({"error": "Неверный ID"}, status=400)
    p, wl, heroes, recent, names = await asyncio.gather(
        api.get(f"/players/{acc}"),
        api.get(f"/players/{acc}/wl"),
        api.get(f"/players/{acc}/heroes"),
        api.get(f"/players/{acc}/recentMatches", ttl=30),
        api.hero_names(),
    )
    if not p or not p.get("profile"):
        return web.json_response({"error": "Профиль не найден или недоступен"}, status=404)
    wl = wl or {}
    return web.json_response({
        "name": p["profile"].get("personaname") or str(acc),
        "rank": rank(p.get("rank_tier")),
        "win": wl.get("win", 0),
        "lose": wl.get("lose", 0),
        "heroes": [
            {"name": names.get(int(h["hero_id"]), "?"), "games": h["games"], "win": h["win"]}
            for h in (heroes or [])[:5] if h["games"]
        ],
        "matches": [
            {
                "id": m["match_id"], "hero": names.get(m["hero_id"], "?"), "win": is_win(m),
                "k": m["kills"], "d": m["deaths"], "a": m["assists"], "duration": m["duration"],
            }
            for m in (recent or [])[:10]
        ],
    })


def make_app():
    app = web.Application()
    app.add_routes([
        web.get("/", health),
        web.get("/health", health),
        web.get("/app", index),
        web.get("/api/profile/{acc}", profile),
    ])
    return app
