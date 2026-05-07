# FunPayCardinal + AutoStars Plugin

FunPayCardinal is a Telegram-controlled bot for automating FunPay marketplace operations, with the AutoStars plugin for automated star sales.

## Run & Operate

- **Start**: workflow `Start application` runs `bash start.sh`
- `start.sh` activates `/opt/venv` if present, generates `configs/_main.cfg` and `plugins/stars_config.json` from env vars, then runs `python main.py`
- **Required secrets** (set in Replit Secrets):
  - `FUNPAY_GOLDEN_KEY` — 32-char FunPay session token (from EditThisCookie on funpay.com)
  - `TG_BOT_TOKEN` — Telegram bot token from @BotFather (bot @username must start with `funpay`)
  - `TG_BOT_PASSWORD` — bot password (8+ chars, upper+lower+digit); used to log in via Telegram
- **Optional secret**: `FUNPAY_USER_AGENT` — custom browser User-Agent string

## Stack

- Python 3.12
- FunPayAPI (bundled), pyTelegramBotAPI 4.15.2, aiohttp 3.10.2, pydantic 1.9.0
- Open-source AutoStars plugin (AutoStars.py) — self-installs its dependencies at runtime

## Where things live

- `plugins/AutoStars.py` — AutoStars plugin (open-source, tracked in git)
- `plugins/stars_config.json` — AutoStars config (NOT in git; generated from env vars on Railway)
- `plugins/stars_stats.json` — AutoStars statistics (NOT in git; auto-created at runtime)
- `configs/_main.cfg` — generated at startup from env vars (do not commit)
- `configs/auto_response.cfg`, `configs/auto_delivery.cfg` — empty by default
- `storage/cache/auto_stars_id.json` — AutoStars plugin cache (auto-created at runtime)
- `generate_config.py` — generates `configs/_main.cfg` from env vars
- `generate_stars_config.py` — generates `plugins/stars_config.json` from env vars (Railway)
- `hash_password.py` — helper to compute TG_SECRET_HASH from a plain password

## Architecture decisions

- Config is generated at startup from env vars rather than using interactive `first_setup.py`, making it suitable for cloud deployment (Railway, Replit)
- `start.sh` only regenerates `configs/_main.cfg` if it doesn't already exist (safe to restart)
- `stars_config.json` is always regenerated from env vars if `STARS_MNEMONIC` is set (Railway)
- Fragment hash is auto-refreshed at startup and hourly via background thread
- Python 3.12 required

## Railway Deployment

Set these environment variables in Railway (in addition to the standard FunPayCardinal vars):

| Variable | Required | Description |
|---|---|---|
| `FUNPAY_GOLDEN_KEY` | ✅ | 32-char FunPay session token |
| `TG_BOT_TOKEN` | ✅ | Telegram bot token |
| `TG_BOT_PASSWORD` | ✅ | Bot password (8+ chars, upper+lower+digit) |
| `STARS_MNEMONIC` | ✅ | 24 mnemonic words space-separated (TON wallet) |
| `STARS_USER_ID` | ✅ | Your Telegram user ID (for admin notifications) |
| `STARS_FRAGMENT_COOKIE` | ✅ | Full fragment.com cookie string with stel_ton_token |
| `STARS_FRAGMENT_HASH` | optional | Fragment API hash (auto-refreshed at startup) |
| `STARS_API_KEY` | optional | TON API key |
| `STARS_DESTINATION_ADDRESS` | optional | TON destination address |
| `STARS_SUBCATEGORY_ID` | optional | FunPay subcategory ID (default: 2418) |
| `STARS_AUTO_REFUND` | optional | true/false (default: false) |

After setting vars, redeploy on Railway. Check deploy logs for `[generate_stars_config]` lines to confirm the config was built from your env vars.

## Product

- FunPayCardinal: auto-response, auto-delivery, order management on FunPay marketplace
- AutoStars plugin: automated Telegram star sales

## Gotchas

- **Fragment "Access denied"**: means `stel_ton_token` in cookie is expired. Go to fragment.com/stars/buy, connect Tonkeeper, copy fresh cookies, update via bot `/stars_config` → Настройки → 🍪 Куки (on Replit) or update `STARS_FRAGMENT_COOKIE` env var (on Railway)
- The bot's Telegram @username must start with `funpay` (BotFather requirement for this bot)
- `FUNPAY_GOLDEN_KEY` must be exactly 32 characters
- `TG_BOT_PASSWORD` must have uppercase + lowercase + digit (min 8 chars)
- If `configs/_main.cfg` exists from a previous run, delete it to regenerate from updated env vars
- `STARS_MNEMONIC` must be exactly 24 words space-separated
- On Railway: if `STARS_MNEMONIC` is not set, `stars_config.json` uses plugin defaults (wrong wallet/cookie)
