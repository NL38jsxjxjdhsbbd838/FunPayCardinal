"""
Generates configs/_main.cfg from environment variables before starting FunPayCardinal.
Required env vars:
  FUNPAY_GOLDEN_KEY  - 32-char token from FunPay account (EditThisCookie)
  TG_BOT_TOKEN       - Telegram bot token from @BotFather
  TG_BOT_PASSWORD    - Password for the Telegram bot (8+ chars, upper+lower+digit)
Optional:
  FUNPAY_USER_AGENT  - custom User-Agent string
"""
import os
import sys
sys.path.insert(0, ".")
from configparser import ConfigParser
from Utils.cardinal_tools import hash_password

def main():
    golden_key = os.environ.get("FUNPAY_GOLDEN_KEY", "").strip()
    tg_token = os.environ.get("TG_BOT_TOKEN", "").strip()
    tg_password = os.environ.get("TG_BOT_PASSWORD", "").strip()
    user_agent = os.environ.get("FUNPAY_USER_AGENT", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/109.0.0.0 Safari/537.36").strip()

    if not golden_key:
        print("[generate_config] ERROR: FUNPAY_GOLDEN_KEY env var is not set.")
        sys.exit(1)
    if len(golden_key) != 32:
        print(f"[generate_config] ERROR: FUNPAY_GOLDEN_KEY must be 32 characters long (got {len(golden_key)}).")
        sys.exit(1)
    if not tg_token:
        print("[generate_config] ERROR: TG_BOT_TOKEN env var is not set.")
        sys.exit(1)
    if not tg_password:
        print("[generate_config] ERROR: TG_BOT_PASSWORD env var is not set.")
        sys.exit(1)
    if (len(tg_password) < 8 or tg_password.lower() == tg_password or
            tg_password.upper() == tg_password or not any(c.isdigit() for c in tg_password)):
        print("[generate_config] ERROR: TG_BOT_PASSWORD must be 8+ chars with uppercase, lowercase, and a digit.")
        sys.exit(1)

    tg_secret_hash = hash_password(tg_password)

    os.makedirs("configs", exist_ok=True)

    config = ConfigParser(delimiters=(":",), interpolation=None)
    config.optionxform = str

    config.read_dict({
        "FunPay": {
            "golden_key": golden_key,
            "user_agent": user_agent,
            "autoRaise": "0",
            "autoResponse": "0",
            "autoDelivery": "0",
            "multiDelivery": "0",
            "autoRestore": "0",
            "autoDisable": "0",
            "oldMsgGetMode": "0",
            "locale": "ru"
        },
        "Telegram": {
            "enabled": "1",
            "token": tg_token,
            "secretKeyHash": tg_secret_hash,
            "blockLogin": "0"
        },
        "BlockList": {
            "blockDelivery": "0",
            "blockResponse": "0",
            "blockNewMessageNotification": "0",
            "blockNewOrderNotification": "0",
            "blockCommandNotification": "0"
        },
        "NewMessageView": {
            "includeMyMessages": "1",
            "includeFPMessages": "1",
            "includeBotMessages": "0",
            "notifyOnlyMyMessages": "0",
            "notifyOnlyFPMessages": "0",
            "notifyOnlyBotMessages": "0",
            "showImageName": "1"
        },
        "Greetings": {
            "ignoreSystemMessages": "0",
            "onlyNewChats": "0",
            "sendGreetings": "0",
            "greetingsText": "Привет, $chat_name!",
            "greetingsCooldown": "2"
        },
        "OrderConfirm": {
            "watermark": "1",
            "sendReply": "0",
            "replyText": "$username, спасибо за подтверждение заказа $order_id!\nЕсли не сложно, оставь, пожалуйста, отзыв!"
        },
        "ReviewReply": {
            "star1Reply": "0",
            "star2Reply": "0",
            "star3Reply": "0",
            "star4Reply": "0",
            "star5Reply": "0",
            "star1ReplyText": "",
            "star2ReplyText": "",
            "star3ReplyText": "",
            "star4ReplyText": "",
            "star5ReplyText": ""
        },
        "Proxy": {
            "enable": "0",
            "ip": "",
            "port": "",
            "login": "",
            "password": "",
            "check": "0"
        },
        "Other": {
            "watermark": "🐦",
            "requestsDelay": "4",
            "language": "ru"
        }
    })

    with open("configs/_main.cfg", "w", encoding="utf-8") as f:
        config.write(f)

    print("[generate_config] configs/_main.cfg written successfully.")

if __name__ == "__main__":
    main()
