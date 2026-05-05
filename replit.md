# FunPayCardinal + AutoStars Plugin

FunPayCardinal is a Telegram-controlled bot for automating FunPay marketplace operations, with the AutoStars plugin for automated star sales.

## Run & Operate

- **Start**: workflow `Start application` runs `bash start.sh`
- `start.sh` generates `configs/_main.cfg` from env vars (if missing), then runs `python main.py`
- **Required secrets** (set in Replit Secrets):
  - `FUNPAY_GOLDEN_KEY` — 32-char FunPay session token (from EditThisCookie on funpay.com)
  - `TG_BOT_TOKEN` — Telegram bot token from @BotFather (bot @username must start with `funpay`)
  - `TG_BOT_PASSWORD` — bot password (8+ chars, upper+lower+digit); used to log in via Telegram
- **Optional secret**: `FUNPAY_USER_AGENT` — custom browser User-Agent string

## Stack

- Python 3.12
- FunPayAPI (bundled), pyTelegramBotAPI 4.15.2, aiohttp 3.10.2, pydantic 1.9.0
- PyArmor-obfuscated plugin (AutoStars.py) — requires pyarmor_runtime_011038 in plugins/

## Where things live

- `plugins/AutoStars.py` — obfuscated AutoStars plugin
- `plugins/AutoStars.sig` — plugin integrity/license signature file
- `plugins/pyarmor_runtime_011038/` — PyArmor runtime (linux x86_64 .so)
- `configs/_main.cfg` — generated at startup from env vars (do not commit)
- `configs/auto_response.cfg`, `configs/auto_delivery.cfg` — empty by default
- `storage/cache/auto_stars_id.json` — AutoStars plugin cache
- `generate_config.py` — generates `configs/_main.cfg` from env vars
- `hash_password.py` — helper to compute TG_SECRET_HASH from a plain password

## Architecture decisions

- Config is generated at startup from env vars rather than using interactive `first_setup.py`, making it suitable for cloud deployment (Railway, Replit)
- `start.sh` only regenerates `configs/_main.cfg` if it doesn't already exist (safe to restart)
- PyArmor runtime directory name must be exactly `pyarmor_runtime_011038` (not `pyamor_runtime_011038`)
- Python 3.12 required (PyArmor .so compiled for 3.12, plugin specified in runtime.txt)

## Product

- FunPayCardinal: auto-response, auto-delivery, order management on FunPay marketplace
- AutoStars plugin: automated Telegram star sales; controlled via `/activate_autostars <key>` command in Telegram

## Gotchas

- **Activate AutoStars**: send `/activate_autostars <your_license_key>` to the Telegram bot after first start
- Plugin loads but shows "License verification failed" until activated — this is normal
- The bot's Telegram @username must start with `funpay` (BotFather requirement for this bot)
- `FUNPAY_GOLDEN_KEY` must be exactly 32 characters
- `TG_BOT_PASSWORD` must have uppercase + lowercase + digit (min 8 chars)
- If `configs/_main.cfg` exists from a previous run, delete it to regenerate from updated env vars
