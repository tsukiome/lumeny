# Lumeny: Dota 2 бот для Telegram

Команды: /start, /dota, /link, /profile, /matches, /match, /watch, /unwatch, /watchlist, /quiz, /top, /app.

## Запуск на Render
1. Залей проект в GitHub-репозиторий.
2. Render → New → Blueprint (или Web Service), выбери репозиторий.
3. Переменные: BOT_TOKEN (от @BotFather), по желанию OPENDOTA_KEY.
4. Render сам задаёт RENDER_EXTERNAL_URL, по нему открывается мини-апп.
5. Для базы, которая переживает деплой: подключи Disk и задай DB_PATH=/data/bot.db.

## Локально
```
pip install -r requirements.txt
BOT_TOKEN=... python main.py
```
Мини-апп в Telegram требует https: локально используй ngrok и задай BASE_URL.
