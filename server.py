import asyncio
import hashlib
import hmac
import json
import os
import random
import time
from urllib.parse import parse_qsl
from pathlib import Path
import aiohttp
from aiohttp import web
from dota import api, db
from dota.fmt import rank, is_win

WEB = Path(__file__).parent / "webapp"


ROLES = ["Керри", "Мид", "Оффлейн", "Саппорт 4", "Саппорт 5"]
RANKS = ["Herald", "Guardian", "Crusader", "Archon", "Legend", "Ancient", "Divine", "Immortal"]
TIMES = ["Утро", "День", "Вечер", "Ночь"]


def tg_user(request):
    """Проверяет подпись Telegram и возвращает пользователя или None."""
    pairs = dict(parse_qsl(request.headers.get("X-Init-Data", ""), keep_blank_values=True))
    h = pairs.pop("hash", None)
    if not h:
        return None
    check = "\n".join(f"{k}={v}" for k, v in sorted(pairs.items()))
    secret = hmac.new(b"WebAppData", os.environ["BOT_TOKEN"].encode(), hashlib.sha256).digest()
    if not hmac.compare_digest(hmac.new(secret, check.encode(), hashlib.sha256).hexdigest(), h):
        return None
    try:
        return json.loads(pairs["user"])
    except Exception:
        return None


async def party_get(request):
    u = tg_user(request)
    if not u:
        return web.json_response({"error": "Открой мини-апп из Telegram"}, status=401)
    role = request.query.get("role")
    return web.json_response({"mine": await db.party_get(u["id"]),
                              "list": await db.party_list(role if role in ROLES else None)})


async def party_post(request):
    u = tg_user(request)
    if not u:
        return web.json_response({"error": "Открой мини-апп из Telegram"}, status=401)
    try:
        b = await request.json()
    except Exception:
        return web.json_response({"error": "Неверные данные"}, status=400)
    if b.get("role") not in ROLES or b.get("rank") not in RANKS or b.get("time") not in TIMES:
        return web.json_response({"error": "Заполни роль, ранг и время"}, status=400)
    name = (u.get("first_name") or "Игрок")[:40]
    await db.party_save(u["id"], u.get("username"), name, b["role"], b["rank"], b["time"],
                        str(b.get("note", ""))[:120])
    return web.json_response({"ok": True})


async def party_del(request):
    u = tg_user(request)
    if not u:
        return web.json_response({"error": "Открой мини-апп из Telegram"}, status=401)
    await db.party_delete(u["id"])
    return web.json_response({"ok": True})


CDN = "https://cdn.cloudflare.steamstatic.com"
_news = {"t": 0, "d": []}


async def quiz(request):
    stats = await api.hero_stats()
    if len(stats) < 4:
        return web.json_response({"error": "Не удалось загрузить героев"}, status=503)
    opts = random.sample(stats, 4)
    right = random.choice(opts)
    image = CDN + right["img"]
    if request.query.get("mode") == "ability":
        ha = await api.get("/constants/hero_abilities", ttl=86400) or {}
        ab = await api.get("/constants/abilities", ttl=86400) or {}
        names = [a for a in (ha.get(right["name"], {}).get("abilities") or [])
                 if a in ab and ab[a].get("img") and not a.startswith("generic_hidden")]
        if names:
            image = CDN + ab[random.choice(names)]["img"]
    return web.json_response({"image": image, "answer": right["id"],
                              "options": [{"id": o["id"], "name": o["localized_name"]} for o in opts]})


async def news(request):
    if time.time() - _news["t"] > 900:
        try:
            url = "https://api.steampowered.com/ISteamNews/GetNewsForApp/v2/?appid=570&count=8&maxlength=1"
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=15)) as s:
                async with s.get(url) as r:
                    j = await r.json()
            _news["d"] = [{"title": i["title"], "url": i["url"], "date": i["date"]}
                          for i in j["appnews"]["newsitems"]]
            _news["t"] = time.time()
        except Exception:
            pass
    return web.json_response(_news["d"])


async def health(request):
    return web.Response(text="ok")


async def index(request):
    return web.FileResponse(WEB / "index.html")


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


async def heroes(request):
    names = await api.hero_names()
    return web.json_response([{"id": i, "name": n} for i, n in sorted(names.items(), key=lambda x: x[1])])


async def pick(request):
    try:
        enemies = [int(x) for x in request.query.get("enemies", "").split(",") if x][:5]
    except ValueError:
        return web.json_response([], status=400)
    if not enemies:
        return web.json_response([])
    names = await api.hero_names()
    data = await asyncio.gather(*[api.get(f"/heroes/{e}/matchups", ttl=3600) for e in enemies])
    score = {}
    for rows in data:
        for r in rows or []:
            if r["games_played"] >= 100:
                score.setdefault(r["hero_id"], []).append(1 - r["wins"] / r["games_played"])
    res = [{"name": names.get(h, "?"), "wr": round(sum(v) / len(v) * 100, 1)}
           for h, v in score.items() if h not in enemies and len(v) == len(enemies)]
    res.sort(key=lambda x: -x["wr"])
    return web.json_response(res[:8])


def make_app():
    app = web.Application()
    app.add_routes([
        web.get("/", health),
        web.get("/health", health),
        web.get("/app", index),
        web.get("/api/profile/{acc}", profile),
        web.get("/api/heroes", heroes),
        web.get("/api/pick", pick),
        web.get("/api/quiz", quiz),
        web.get("/api/news", news),
        web.get("/api/party", party_get),
        web.post("/api/party", party_post),
        web.delete("/api/party", party_del),
    ])
    return app
