import os
import time
import aiohttp

BASE = "https://api.opendota.com/api"
KEY = os.getenv("OPENDOTA_KEY")  # необязательно, но снимает лимиты
_cache = {}
STEAM64 = 76561197960265728


def to_account_id(raw):
    """Принимает friend ID или Steam64, возвращает account_id или None."""
    if not raw or not raw.strip().isdigit():
        return None
    n = int(raw.strip())
    return n - STEAM64 if n > STEAM64 else n


async def get(path, ttl=60):
    now = time.time()
    hit = _cache.get(path)
    if hit and now - hit[0] < ttl:
        return hit[1]
    url = BASE + path
    if KEY:
        url += ("&" if "?" in url else "?") + f"api_key={KEY}"
    try:
        timeout = aiohttp.ClientTimeout(total=15)
        async with aiohttp.ClientSession(timeout=timeout) as s:
            async with s.get(url) as r:
                if r.status != 200:
                    return None
                data = await r.json()
    except Exception:
        return None
    _cache[path] = (now, data)
    return data


async def hero_names():
    data = await get("/heroes", ttl=86400) or []
    return {h["id"]: h["localized_name"] for h in data}


async def hero_stats():
    return await get("/heroStats", ttl=86400) or []
