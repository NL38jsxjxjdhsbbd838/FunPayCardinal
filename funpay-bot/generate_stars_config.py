"""
Generates plugins/stars_config.json from environment variables.
Called by start.sh when STARS_MNEMONIC env var is set (Railway/cloud deployment).

Required env vars:
  STARS_MNEMONIC              — 24 mnemonic words, space-separated
  STARS_USER_ID               — Telegram user ID for admin notifications
  STARS_FRAGMENT_COOKIE       — Full fragment.com cookie string (stel_ssid=...; stel_ton_token=...)

Optional env vars:
  STARS_FRAGMENT_HASH         — Fragment API hash (auto-refreshed at startup if missing)
  STARS_API_KEY               — TON API key (uses default if not set)
  STARS_DESTINATION_ADDRESS   — TON wallet address for destination
  STARS_SUBCATEGORY_ID        — FunPay subcategory ID (default: 2418)
  STARS_AUTO_REFUND           — true/false (default: false)
"""

import json
import os
import sys

CONFIG_FILE = "plugins/stars_config.json"

DEFAULT_API_KEY = "AEKSKPT6TKLI4NYAAAAHPHNHMLEWALZ35P5DCOHNHBGBIFHIZPP3WPOXECHUKQOQQRIPANY"
DEFAULT_DESTINATION = "UQBSnpieL5S6CcsErpKF8EI0x-1GqlbkINnw9D3hbebeO8nc"
DEFAULT_COMPLETED_MESSAGE = (
    "✅ Заказ выполнен!\n"
    "🔗 Транзакция: {ton_viewer_url}\n"
    "⭐️ Отправлено Stars: {quantity}\n"
    "🔑 Ref ID: Ref#{ref_id}\n\n"
    "Пожалуйста, подтвердите заказ: https://funpay.com/orders/{orderID}/"
)
DEFAULT_QUANTITIES = [10, 15, 25, 50, 75, 100, 150, 200, 250, 350, 500, 1000, 2500]

mnemonic_raw = os.environ.get("STARS_MNEMONIC", "").strip()
if not mnemonic_raw:
    print("[generate_stars_config] STARS_MNEMONIC not set — skipping stars_config.json generation.")
    sys.exit(0)

mnemonic = mnemonic_raw.split()
if len(mnemonic) != 24:
    print(f"[generate_stars_config] WARNING: STARS_MNEMONIC has {len(mnemonic)} words (expected 24). Proceeding anyway.")

user_id_raw = os.environ.get("STARS_USER_ID", "").strip()
if not user_id_raw:
    print("[generate_stars_config] WARNING: STARS_USER_ID not set — admin Telegram notifications won't work.")
    user_id = 0
else:
    try:
        user_id = int(user_id_raw)
    except ValueError:
        print(f"[generate_stars_config] WARNING: STARS_USER_ID is not an integer: {user_id_raw!r}")
        user_id = 0

fragment_cookie = os.environ.get("STARS_FRAGMENT_COOKIE", "").strip()
if not fragment_cookie:
    print("[generate_stars_config] WARNING: STARS_FRAGMENT_COOKIE not set — Fragment API will fail with 'Access denied'.")

fragment_hash = os.environ.get("STARS_FRAGMENT_HASH", "71045684dda1a6061f").strip()
api_key = os.environ.get("STARS_API_KEY", DEFAULT_API_KEY).strip()
destination = os.environ.get("STARS_DESTINATION_ADDRESS", DEFAULT_DESTINATION).strip()
subcategory_id = int(os.environ.get("STARS_SUBCATEGORY_ID", "2418"))
auto_refund = os.environ.get("STARS_AUTO_REFUND", "false").strip().lower() == "true"

existing_config = {}
if os.path.exists(CONFIG_FILE):
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            existing_config = json.load(f)
        print(f"[generate_stars_config] Existing {CONFIG_FILE} found — merging with env vars.")
    except Exception as e:
        print(f"[generate_stars_config] Could not read existing config: {e}")

config = {
    "API_KEY": api_key,
    "IS_TESTNET": False,
    "MNEMONIC": mnemonic,
    "DESTINATION_ADDRESS": destination,
    "ALLOWED_QUANTITIES": existing_config.get("ALLOWED_QUANTITIES", DEFAULT_QUANTITIES),
    "fragment_api": {
        "hash": fragment_hash,
        "cookie": fragment_cookie,
        "url": "https://fragment.com/api",
        "subcategory_id": subcategory_id,
    },
    "user_id": user_id,
    "completed_order_message": existing_config.get("completed_order_message", DEFAULT_COMPLETED_MESSAGE),
    "AUTO_REFUND": auto_refund,
    "SHOW_SENDER": existing_config.get("SHOW_SENDER", "0"),
    "USE_OLD_BALANCE": existing_config.get("USE_OLD_BALANCE", False),
}

os.makedirs(os.path.dirname(CONFIG_FILE), exist_ok=True)
with open(CONFIG_FILE, "w", encoding="utf-8") as f:
    json.dump(config, f, indent=4, ensure_ascii=False)

print(f"[generate_stars_config] {CONFIG_FILE} written successfully.")
print(f"  MNEMONIC: {mnemonic[0]} {mnemonic[1]} ... ({len(mnemonic)} words)")
print(f"  USER_ID:  {user_id}")
print(f"  FRAGMENT_HASH: {fragment_hash}")
print(f"  FRAGMENT_COOKIE set: {'yes' if fragment_cookie else 'NO — will fail!'}")
