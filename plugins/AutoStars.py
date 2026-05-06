# -*- coding: utf-8 -*-
from __future__ import annotations

import asyncio
import threading
import logging
from logging import Filter
import requests
import json
import os
import base64
import re
import io
import datetime
import time
import random
import subprocess
import sys
import atexit
from typing import TYPE_CHECKING, Dict, List, Tuple, Optional

def _pip_install(*packages: str):
    """Устанавливает пакеты в то же окружение, где запущен Cardinal."""
    # Ищем pip в venv Cardinal (/opt/venv), затем fallback на sys.executable
    candidates = [
        "/opt/venv/bin/pip",
        os.path.join(os.path.dirname(sys.executable), "pip"),
        sys.executable,
    ]
    pip_exec = None
    for c in candidates:
        if os.path.isfile(c):
            pip_exec = c
            break

    if pip_exec and pip_exec.endswith("pip"):
        cmd = [pip_exec, "install", "--quiet"] + list(packages)
    else:
        cmd = [sys.executable, "-m", "pip", "install", "--quiet"] + list(packages)

    for extra in (["--break-system-packages"], []):
        try:
            subprocess.check_call(cmd + extra,
                                  stdout=subprocess.DEVNULL,
                                  stderr=subprocess.DEVNULL)
            return
        except subprocess.CalledProcessError:
            continue
    raise RuntimeError(f"[AutoStars] Не удалось установить: {packages}")


try:
    import matplotlib.pyplot as plt
except Exception as _mpl_err:
    import traceback
    print(f"[AutoStars] Ошибка импорта matplotlib: {_mpl_err}")
    traceback.print_exc()
    try:
        _pip_install("matplotlib")
        import matplotlib.pyplot as plt
    except Exception as _mpl_err2:
        traceback.print_exc()
        raise ImportError(f"[AutoStars] Не удалось импортировать matplotlib: {_mpl_err2}")

try:
    import pymysql
except ImportError:
    pymysql = None

try:
    from tonutils.client import TonapiClient
    from tonutils.wallet import WalletV5R1
except Exception as _tonutils_err:
    import traceback
    print(f"[AutoStars] Ошибка импорта tonutils: {_tonutils_err}")
    traceback.print_exc()
    try:
        print("[AutoStars] Переустановка tonutils...")
        _pip_install("tonutils")
        from tonutils.client import TonapiClient
        from tonutils.wallet import WalletV5R1
    except Exception as _tonutils_err2:
        traceback.print_exc()
        raise ImportError(f"[AutoStars] Не удалось импортировать tonutils: {_tonutils_err2}")

try:
    import httpx
except ImportError:
    print("[AutoStars] Установка httpx...")
    _pip_install("httpx")
    import httpx

try:
    from FunPayAPI.updater.events import NewOrderEvent, NewMessageEvent
    from FunPayAPI import Account, enums
    from telebot import types
    from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
    import telebot
    import FunPayAPI
except ImportError as e:
    print(f"[AutoStars] Ошибка импорта FunPayAPI/telebot: {e}")
    _pip_install("pyTelegramBotAPI")
    from FunPayAPI.updater.events import NewOrderEvent, NewMessageEvent
    from FunPayAPI import Account, enums
    from telebot import types
    from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
    import telebot
    import FunPayAPI

if TYPE_CHECKING:
    from cardinal import Cardinal

if sys.platform == 'win32':
    try:
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    except Exception:
        pass

CONFIG_FILE = "plugins/stars_config.json"


def sanitize_telegram_text(text: str) -> str:
    text = text.replace("<", "<").replace(">", ">")
    text = text.encode("utf-8", errors="replace").decode("utf-8", errors="replace")
    return text

ADDRESS = "UQAfXuJ9sT8rMJMIlGcPjvTxwdnBvB7ygLknN87TnS-taYwR"
default_config = {
    "API_KEY": "AEKSKPT6TKLI4NYAAAAHPHNHMLEWALZ35P5DCOHNHBGBIFHIZPP3WPOXECHUKQOQQRIPANY",
    "IS_TESTNET": False,
    "MNEMONIC": [
        "second", "denial", "denial", "crop", "captain", "narrow",
        "figure", "sleep", "enact", "wisdom", "slice", "chimney",
        "soft", "maximum", "lesson", "icon", "laugh", "swim",
        "true", "penalty", "yellow", "neutral", "drama", "possible"
    ],
    "DESTINATION_ADDRESS": "UQBSnpieL5S6CcsErpKF8EI0x-1GqlbkINnw9D3hbebeO8nc",
    "ALLOWED_QUANTITIES": [10, 15, 25, 50, 75, 100, 150, 200, 250, 350, 500, 1000, 2500],
    "fragment_api": {
        "hash": "71045684dda1a6061f",
        "cookie": "stel_ssid=2917e8b9821a5295d1_17976481239295292623; stel_dt=-180; stel_token=5298b6ddf12e9d4c3ab2be69f00630e05298b6c75298b5c9bdf3ee61c9aa8eced23bf; stel_ton_token=u0-zatulVO2xWKpk0hcfA4W3niLYo-tc8YXU_AILlcBVSouIxI6Cg35abIq6IWBxjFK-LDMkTHUFziugDQV-UMv8Rvw6A1RxoZ3KMddqUyVmUi3FC4pY-1g8ZY_XU7Sxouzqeh_qFe2ohOt-QhkMF7fDAnqglbk862okSCH-Z1cCeovFK7vZzGWIZyDJe8-o9jvrQf1n",
        "url": "https://fragment.com/api",
        "subcategory_id": 2418
    },
    "user_id": 7911419734 ,
    "completed_order_message": """✅ Заказ выполнен!
🔗 Транзакция: {ton_viewer_url}
⭐️ Отправлено Stars: {quantity}
🔑 Ref ID: Ref#{ref_id}

Пожалуйста, подтвердите заказ: https://funpay.com/orders/{orderID}/
""",
    "AUTO_REFUND": False,
    "SHOW_SENDER": "0",
    "USE_OLD_BALANCE": False
}


def load_config() -> dict:
    os.makedirs(os.path.dirname(CONFIG_FILE), exist_ok=True)
    if not os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(default_config, f, indent=4, ensure_ascii=False)
    with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
        config = json.load(f)
    for key in default_config:
        if key not in config:
            config[key] = default_config[key]
    if "fragment_api" not in config:
        config["fragment_api"] = default_config["fragment_api"]
    else:
        for frag_key in default_config["fragment_api"]:
            if frag_key not in config["fragment_api"]:
                config["fragment_api"][frag_key] = default_config["fragment_api"][frag_key]
    if "user_id" not in config:
        config["user_id"] = default_config["user_id"]
    if "completed_order_message" not in config:
        config["completed_order_message"] = default_config["completed_order_message"]
    if "AUTO_REFUND" not in config:
        config["AUTO_REFUND"] = default_config["AUTO_REFUND"]
    if "SHOW_SENDER" not in config:
        config["SHOW_SENDER"] = default_config["SHOW_SENDER"]
    if "USE_OLD_BALANCE" not in config:
        config["USE_OLD_BALANCE"] = default_config["USE_OLD_BALANCE"]
    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(config, f, indent=4, ensure_ascii=False)
    return config


try:
    config = load_config()
except Exception as _cfg_err:
    print(f"[AutoStars] Ошибка загрузки конфига, используется дефолтный: {_cfg_err}")
    config = default_config.copy()

API_KEY = config["API_KEY"]
IS_TESTNET = config["IS_TESTNET"]
MNEMONIC: list[str] = config["MNEMONIC"]
DESTINATION_ADDRESS = config["DESTINATION_ADDRESS"]
ALLOWED_QUANTITIES = config["ALLOWED_QUANTITIES"]
USER_ID = config["user_id"]
COMPLETED_ORDER_MESSAGE = config["completed_order_message"]
SHOW_SENDER = config["SHOW_SENDER"]

logger = logging.getLogger("FPC.autostars")
logger.setLevel(logging.DEBUG)

FRAGMENT_HASH = config["fragment_api"]["hash"]
FRAGMENT_COOKIE = config["fragment_api"]["cookie"]
FRAGMENT_URL = config["fragment_api"]["url"]
SUBCATEGORY_ID = config["fragment_api"].get("subcategory_id", 2418)

url = f"{FRAGMENT_URL}?hash={FRAGMENT_HASH}"
headers = {
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "Accept-Encoding": "gzip, deflate, br, zstd",
    "Accept-Language": "ru",
    "Connection": "keep-alive",
    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
    "Cookie": FRAGMENT_COOKIE,
    "Host": "fragment.com",
    "Origin": "https://fragment.com",
    "Referer": "https://fragment.com/stars/buy",
    "Sec-Fetch-Dest": "empty",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Site": "same-origin",
    "User-Agent": "Mozilla/5.0 (Windows NT 6.1; Win64; x64; rv:131.0) Gecko/20010101 Firefox/131.0",
    "X-Requested-With": "XMLHttpRequest"
}

def decoder(data: str) -> bytes:
    while len(data) % 4 != 0:
        data += "="
    return base64.b64decode(data)


def decoder2(data: bytes) -> str:
    decoded_data = data.decode('latin1')
    ref_id = decoded_data.split("Ref#")[-1]
    return ref_id


def remove_at_symbol(username: str) -> str:
    if username.startswith('@'):
        return username[1:]
    return username


def generate_order_graph(date_str: str) -> io.BytesIO:
    if date_str not in stats_data:
        return None

    day_stats = stats_data[date_str]
    successful = day_stats.get("successful_transactions", 0)
    unsuccessful = day_stats.get("unsuccessful_transactions", 0)
    quantities = day_stats.get("quantities_sold", {})

    categories = list(quantities.keys())
    quantities_sold = list(quantities.values())

    fig, ax = plt.subplots(figsize=(8, 6))

    ax.bar(['Успешные', 'Неуспешные'], [successful, unsuccessful], color=['green', 'red'], label="Статус заказов")

    ax2 = ax.twinx()
    ax2.bar(categories, quantities_sold, color='blue', alpha=0.5, label="Количество Stars")

    ax.set_xlabel('Типы заказов')
    ax.set_ylabel('Количество заказов')
    ax2.set_ylabel('Количество проданных Stars')

    plt.title(f"Статистика заказов и проданных Stars за {date_str}")
    fig.tight_layout()

    image_stream = io.BytesIO()
    plt.savefig(image_stream, format='png')
    image_stream.seek(0)
    plt.close(fig)

    return image_stream


STATS_FILE = "plugins/stars_stats.json"


def load_stats() -> dict:
    os.makedirs(os.path.dirname(STATS_FILE), exist_ok=True)
    if not os.path.exists(STATS_FILE):
        with open(STATS_FILE, 'w', encoding='utf-8') as f:
            json.dump({}, f, ensure_ascii=False)
    with open(STATS_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)


def save_stats(stats_data: dict):
    with open(STATS_FILE, 'w', encoding='utf-8') as f:
        json.dump(stats_data, f, indent=4, ensure_ascii=False)


try:
    stats_data = load_stats()
except Exception as _stats_err:
    print(f"[AutoStars] Ошибка загрузки статистики, используется пустой словарь: {_stats_err}")
    stats_data = {}


def send_error_with_inline_url(c, USER_ID, orderID: str, error: str):
    keyboard = InlineKeyboardMarkup(row_width=1)
    keyboard.add(
        InlineKeyboardButton(
            text="Открыть заказ FunPay",
            url=f"https://funpay.com/orders/{orderID}/"
        )
    )
    keyboard.add(
        InlineKeyboardButton(
            text="Вернуть заказ",
            callback_data=f"refund_order_{orderID}"
        )
    )

    text_message = (
        f"🔴 У вас произошла ошибка в заказе #{orderID}\n"
        f"Ошибка: {error}\n"
        "Просьба вернуть средства"
    )

    c.telegram.bot.send_message(
        USER_ID,
        sanitize_telegram_text(text_message),
        reply_markup=keyboard
    )


def update_stats(success: bool, quantity: int):
    date_str = datetime.datetime.now().strftime("%Y-%m-%d")
    if date_str not in stats_data:
        stats_data[date_str] = {
            "successful_transactions": 0,
            "unsuccessful_transactions": 0,
            "quantities_sold": {},
            "transactions": []
        }
    if success:
        stats_data[date_str]["successful_transactions"] += 1
    else:
        stats_data[date_str]["unsuccessful_transactions"] += 1
    q_str = str(quantity)
    if q_str not in stats_data[date_str]["quantities_sold"]:
        stats_data[date_str]["quantities_sold"][q_str] = 0
    stats_data[date_str]["quantities_sold"][q_str] += 1
    now_time = datetime.datetime.now().strftime("%H:%M:%S")
    stats_data[date_str]["transactions"].append({
        "time": now_time,
        "quantity": quantity,
        "status": "success" if success else "fail"
    })
    save_stats(stats_data)


async def check_wallet_balance() -> float:
    client = TonapiClient(api_key=API_KEY, is_testnet=IS_TESTNET)
    wallet, public_key, private_key, mnemonic = WalletV5R1.from_mnemonic(client, MNEMONIC)
    try:
        balance_nano = await wallet.balance()
    except Exception as e:
        if "404" in str(e) or "entity not found" in str(e).lower():
            logger.debug("Кошелёк ещё не развёрнут в блокчейне (нет транзакций). Баланс: 0.0 TON")
            return 0
        raise
    if config["USE_OLD_BALANCE"]:
        balance_ton = balance_nano
    else:
        balance_ton = balance_nano / 1_000_000_000
    logger.debug(f"Баланс кошелька: {balance_ton} TON")
    return balance_nano


async def send_ton_transaction(amount: float, comment: str, destination_address: str) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    client = TonapiClient(api_key=API_KEY, is_testnet=IS_TESTNET)
    wallet, public_key, private_key, mnemonic = WalletV5R1.from_mnemonic(client, MNEMONIC)
    balance_nano = await check_wallet_balance()
    balance_ton = balance_nano / 1_000_000_000
    if balance_ton < amount:
        error_msg = f"Недостаточно средств на кошельке. Требуется: {amount} TON, доступно: {balance_ton:.4f} TON."
        logger.warning(error_msg)
        return None, None, error_msg

    async def send_transaction_task():
        try:
            tx_hash = await wallet.transfer(
                destination=destination_address,
                amount=amount,
                body=comment,
            )
            logger.info(f"Успешно переведено {amount} TON! TX Hash: {tx_hash}")
            await asyncio.sleep(random.randint(2, 10))
            logger.debug(f"Ссылка Tonviewer: https://tonviewer.com/transaction/{tx_hash}")
            ref_id = comment.split("Ref#")[-1].strip()
            return tx_hash, ref_id, None
        except Exception as e:
            error_msg = f"Ошибка при отправке транзакции: {e}"
            logger.error(error_msg)
            return None, None, error_msg

    task = asyncio.create_task(send_transaction_task())
    result = await task
    return result


async def main_async(username: str, quantity: int) -> Tuple[Optional[str], Optional[str], int, Optional[str]]:
    if quantity:
        clean_username = remove_at_symbol(username)
        logger.debug(f"Очистенный username: {clean_username}")
        payload_search = {
            "query": clean_username,
            "quantity": quantity,
            "method": "searchStarsRecipient"
        }
        logger.debug(f"Payload для поиска recipient: {payload_search}")
        try:
            response_search = requests.post(url, headers=headers, data=payload_search)
            response_search.raise_for_status()
            logger.debug(f"Ответ сервера (поиск recipient): {response_search.text}")
            if not response_search.text:
                error_msg = "Пустой ответ от сервера Fragment при поиске recipient."
                logger.error(error_msg)
                return None, None, quantity, error_msg
            try:
                text_search = response_search.json()
            except json.JSONDecodeError as e:
                error_msg = f"Не удалось декодировать JSON: {e}. Ответ сервера: {response_search.text}"
                logger.error(error_msg)
                return None, None, quantity, error_msg
            logger.debug(f"JSON поиска recipient: {text_search}")
        except requests.RequestException as e:
            error_msg = f"Ошибка при запросе поиска recipient: {e}"
            logger.error(error_msg)
            return None, None, quantity, error_msg
        if text_search.get('ok') is True:
            recipient = text_search.get('found', {}).get('recipient')
            if not recipient:
                error_msg = f"Recipient не найден в ответе: {text_search}"
                logger.error(error_msg)
                return None, None, quantity, error_msg
        else:
            error_detail = text_search.get('error', 'Неизвестная ошибка при поиске recipient.')
            error_msg = f"Ошибка при поиске recipient: {error_detail}"
            logger.error(error_msg)
            return None, None, quantity, error_msg
        payload_init = {
            "recipient": recipient,
            "quantity": quantity,
            "method": "initBuyStarsRequest"
        }
        logger.debug(f"Payload для инициализации покупки: {payload_init}")
        try:
            response_init = requests.post(url, headers=headers, data=payload_init)
            response_init.raise_for_status()
            logger.debug(f"Ответ сервера (инициализация покупки): {response_init.text}")
            if not response_init.text:
                error_msg = "Пустой ответ от сервера Fragment при инициализации покупки."
                logger.error(error_msg)
                return None, None, quantity, error_msg
            try:
                text_init = response_init.json()
            except json.JSONDecodeError as e:
                error_msg = f"Не удалось декодировать JSON: {e}. Ответ сервера: {response_init.text}"
                logger.error(error_msg)
                return None, None, quantity, error_msg
            logger.debug(f"JSON инициализации покупки: {text_init}")
        except requests.RequestException as e:
            error_msg = f"Ошибка при инициализации покупки Stars: {e}"
            logger.error(error_msg)
            return None, None, quantity, error_msg
        req_id = text_init.get('req_id')
        try:
            AMOUNT = float(text_init.get('amount', 0))
            logger.debug(f"Требуемая сумма: {AMOUNT} TON")
        except (TypeError, ValueError):
            AMOUNT = 0
            logger.error("Не удалось конвертировать 'amount' в float.")
        if not req_id or AMOUNT == 0:
            error_msg = f"Не удалось получить req_id или amount: {text_init}"
            logger.error(error_msg)
            return None, None, quantity, error_msg
        payload_link = {
            "account": '{"address":"0:adc5b49f73e4796ecc3c290ad0d89f87fa552b515d173d5295469df9612c24a","chain":"-239","walletStateInit":"te6ccgECFgEAAwQAAgE0AQIBFP8A9KQT9LzyyAsDAFEAAAAAKamjF5hE%2BFriD8Ufe710n9USsAZBzBxLOlXNYCYDiPBRvJZXQAIBIAQFAgFIBgcE%2BPKDCNcYINMf0x%2FT%2F%2FQE0VFDuvKhUVG68qIF%2BQFUEGT5EPKj%2BAAkpMjLH1JAyx9SMMv%2FUhD0AMntVPgPAdMHIcAAn2xRkyDXSpbTB9QC%2BwDoMOAhwAHjACHAAuMAAcADkTDjDQOkyMsfEssfy%2F8SExQVAubQAdDTAyFxsJJfBOAi10nBIJJfBOAC0x8hghBwbHVnvSKCEGRzdHK9sJJfBeAD%2BkAwIPpEAcjKB8v%2FydDtRNCBAUDXIfQEMFyBAQj0Cm%2BhMbOSXwfgBdM%2FyCWCEHBsdWe6kjgw4w0DghBkc3RyupJJfBuMNCAkCASAKCwB4AfoA9AQw%2BCdvIjBQCqEhvvLgUIIQcGx1Z4MesXCAGFAEywUmzxZY%2BgIZ9ADLaRfLH1Jgyz8gyYBA%2BwAGAIpQBIEBCPRZMO1E0IEBQNcgyAHPFvQAye1UAXKwjiOCEGRzdHKDHrFwgBhQBcsFUAPPFiP6AhPLassfyz%2FJgED7AJJfA%2BICASAMDQBZvSQrb2omhAgKBrkPoCGEcNQICEekk30pkQzmkD6f%2BYN4EoAbeBAUiYcVnzGEAgFYDg8AEbjJftRNDXCx%2BAA9sp37UTQgQFA1yH0BDACyMoHy%2F%2FJ0AGBAQj0Cm%2BhMYAIBIBARABmtznaiaEAga5Drhf%2FAABmvHfaiaEAQa5DrhY%2FAAG7SB%2FoA1NQi%2BQAFyMoHFcv%2FydB3dIAYyMsFywIizxZQBfoCFMtrEszMyXP7AMhAFIEBCPRR8qcCAHCBAQjXGPoA0z%2FIVCBHgQEI9FHyp4IQbm90ZXB0gBjIywXLAlAGzxZQBPoCE8tqEszMyXP7AMhAFIEBCPRR8qcCAHCBAQjXGPoA0z%2FIVCBHgQEI9FHyp4IQZHN0cnB0gBjIywXLAlAFzxZQA%2FoCE8tqyx8Syz%2FJc%2FsAAAr0AMntVA%3D%3D"}',
            "device": '{"platform":"android","appName":"Tonkeeper","appVersion":"5.0.18","maxProtocolVersion":2,"features":["SendTransaction",{"name":"SendTransaction","maxMessages":4}]}',
            "transaction": "1",
            "id": req_id,
            "show_sender": SHOW_SENDER,
            "method": "getBuyStarsLink"
        }
        logger.debug(f"Payload для получения ссылки на покупку: {payload_link}")
        try:
            response_link = requests.post(url, headers=headers, data=payload_link)
            response_link.raise_for_status()
            logger.debug(f"Ответ сервера (получение ссылки на покупку): {response_link.text}")
            if not response_link.text:
                error_msg = "Пустой ответ от сервера Fragment при получении ссылки на покупку."
                logger.error(error_msg)
                return None, None, quantity, error_msg
            try:
                text_link = response_link.json()
            except json.JSONDecodeError as e:
                error_msg = f"Не удалось декодировать JSON: {e}. Ответ сервера: {response_link.text}"
                logger.error(error_msg)
                return None, None, quantity, error_msg
            logger.debug(f"JSON получения ссылки на покупку: {text_link}")
        except requests.RequestException as e:
            error_msg = f"Ошибка при получении ссылки на покупку Stars: {e}"
            logger.error(error_msg)
            return None, None, quantity, error_msg
        if text_link.get('ok') is True:
            transaction_messages = text_link.get('transaction', {}).get('messages', [])
            logger.debug(f"Сообщения транзакции: {transaction_messages}")
            if not transaction_messages:
                error_msg = f"Сообщения транзакции не найдены: {text_link}"
                logger.error(error_msg)
                return None, None, quantity, error_msg
            payload_transaction = transaction_messages[0].get('payload')
            address = transaction_messages[0].get('address')
            logger.debug(f"Payload транзакции: {payload_transaction}")
            if not payload_transaction or not address:
                error_msg = f"Payload или address сообщения транзакции не найден: {text_link}"
                logger.error(error_msg)
                return None, None, quantity, error_msg
            try:
                decoded_payload = decoder(payload_transaction)
                ref_id = decoder2(data=decoded_payload)
                COMMENT = f"{quantity} Telegram Stars \n\nRef#{ref_id}"
                logger.debug(f"Комментарий для транзакции: {COMMENT}")
            except Exception as e:
                error_msg = f"Ошибка при обработке payload транзакции: {e}"
                logger.error(error_msg)
                return None, None, quantity, error_msg
        else:
            error_detail = text_link.get('error', 'Неизвестная ошибка при получении ссылки на покупку Stars.')
            error_msg = f"Ошибка при получении ссылки на покупку Stars: {error_detail}"
            logger.error(error_msg)
            return None, None, quantity, error_msg
        try:
            tx_hash, ref_id, error_transaction = await send_ton_transaction(AMOUNT, COMMENT, address)
            if error_transaction:
                return None, None, quantity, error_transaction
            if not tx_hash or not ref_id:
                error_msg = "Не удалось получить данные транзакции после отправки."
                logger.error(error_msg)
                return None, None, quantity, error_msg
        except Exception as e:
            error_msg = f"Исключение при отправке транзакции: {e}"
            logger.error(error_msg)
            return None, None, quantity, error_msg
        return tx_hash, ref_id, quantity, None


orders_info: Dict[int, List[Dict[str, str | int | bool | None]]] = {}


class PaymentProcessor:
    def __init__(self):
        self.loop = asyncio.new_event_loop()
        self.thread = threading.Thread(target=self.run_loop, daemon=True)
        self.thread.start()
        logger.debug("Поток PaymentProcessor запущен.")
        self.task_queue = asyncio.Queue()
        asyncio.run_coroutine_threadsafe(self.queue_worker(), self.loop)

    def run_loop(self):
        asyncio.set_event_loop(self.loop)
        logger.debug("Асинхронный цикл PaymentProcessor запущен.")
        self.loop.run_forever()

    def enqueue_payment(self, c: Cardinal, buyer_chat_id: int, username: str, stars_quantity: int, orderID: str):
        task = (c, buyer_chat_id, username, stars_quantity, orderID)
        position_in_queue = self.task_queue.qsize() + 1
        asyncio.run_coroutine_threadsafe(self.task_queue.put(task), self.loop)
        return position_in_queue

    async def queue_worker(self):
        while True:
            task = await self.task_queue.get()
            try:
                c, buyer_chat_id, username, stars_quantity, orderID = task
                await self.process_payment(c, buyer_chat_id, username, stars_quantity, orderID)
            except Exception as e:
                logger.error(f"[queue_worker] Ошибка при обработке задачи: {e}")
            finally:
                self.task_queue.task_done()

    async def process_payment(self, c: Cardinal, buyer_chat_id: int, username: str, stars_quantity: int, orderID: str):
        retry_count = 0
        max_retries = 3

        while retry_count < max_retries:
            try:
                tx_hash, ref_id, quantity, error = await main_async(username, stars_quantity)
                if error:
                    if '406' in error and 'External message was not accepted' in error:
                        retry_count += 1
                        if retry_count < max_retries:
                            logger.warning(
                                f"Попытка {retry_count}: Ошибка 406 'External message was not accepted', повторная попытка через 5 секунд.")
                            await asyncio.sleep(5)
                            continue
                        else:
                            logger.error(
                                f"Превышено количество попыток ({max_retries}) для заказа {orderID} из-за ошибки 406.")
                            update_stats(False, stars_quantity)
                            # Покупателю — только универсальное сообщение
                            c.send_message(buyer_chat_id, sanitize_telegram_text(
                                "❌ Ваш заказ не выполнен. Деньги возвращены. Пожалуйста, свяжитесь с поддержкой."))
                            if config["AUTO_REFUND"]:
                                c.account.refund(orderID)
                                c.telegram.bot.send_message(USER_ID, sanitize_telegram_text(
                                    f'Вернул пользователю: {username} деньги по причине: {error}'))
                            else:
                                send_error_with_inline_url(c, USER_ID, orderID, error)
                            logger.error(f"[AUTO_STARS] Критическая ошибка: {error} (orderID={orderID})")
                            deactivate_all_lots(c, SUBCATEGORY_ID)
                            return
                    elif 'No Telegram users found' in error:
                        logger.info(f"Username {username} не найден для пользователя {buyer_chat_id}")
                        user_orders = orders_info.get(buyer_chat_id, [])
                        for o in user_orders:
                            if o['orderID'] == orderID and not o.get('completed', False):
                                o['username'] = None
                                o['confirmed'] = False
                                break
                        # Покупателю — только просьба ввести корректный username
                        c.send_message(buyer_chat_id, sanitize_telegram_text(
                            "❌ Указанный вами username не найден в Telegram. Пожалуйста, введите корректный @username для получения Stars."))
                        logger.error(f"[AUTO_STARS] Ошибка: {error} (orderID={orderID})")
                        deactivate_all_lots(c, SUBCATEGORY_ID)
                        return
                    elif 'Не удалось декодировать JSON' in error:
                        logger.error(f"Платёж не удался для {username}: {error}")
                        user_orders = orders_info.get(buyer_chat_id, [])
                        current_order = next(
                            (o for o in user_orders if o['orderID'] == orderID and not o.get('completed', False)), None)
                        if current_order:
                            if 'retry_count' not in current_order:
                                current_order['retry_count'] = 0
                            current_order['retry_count'] += 1
                            if current_order['retry_count'] <= 3:
                                await asyncio.sleep(5)
                                await self.process_payment(c, buyer_chat_id, username, stars_quantity, orderID)
                                return
                            else:
                                logger.error(f"Превышено количество попыток декодирования JSON для заказа {orderID}")
                        else:
                            logger.error(f"Заказ {orderID} не найден в orders_info для buyer_chat_id {buyer_chat_id}")
                        # Покупателю — только универсальное сообщение
                        c.send_message(buyer_chat_id, sanitize_telegram_text(
                            "❌ Ваш заказ не выполнен. Деньги возвращены. Пожалуйста, свяжитесь с поддержкой."))
                        logger.error(f"[AUTO_STARS] Критическая ошибка: {error} (orderID={orderID})")
                        deactivate_all_lots(c, SUBCATEGORY_ID)
                        return
                    elif 'Недостаточно средств на кошельке' in error:
                        # Покупателю — только инфо о возврате
                        c.send_message(buyer_chat_id, sanitize_telegram_text(
                            "❌ На кошельке продавца недостаточно средств. Ваши деньги возвращены."))
                        c.account.refund(orderID)
                        c.telegram.bot.send_message(USER_ID, sanitize_telegram_text(
                            f'Вернул пользователю: {username} деньги по причине: {error}'))
                        logger.error(f"[AUTO_STARS] Недостаточно средств: {error} (orderID={orderID})")
                        deactivate_all_lots(c, SUBCATEGORY_ID)
                        return
                    else:
                        update_stats(False, stars_quantity)
                        c.send_message(buyer_chat_id,
                                       sanitize_telegram_text("❌ Ваш заказ не выполнен. Деньги возвращены. Пожалуйста, свяжитесь с поддержкой."))
                        if config["AUTO_REFUND"]:
                            c.account.refund(orderID)
                            c.telegram.bot.send_message(USER_ID, sanitize_telegram_text(
                                f'Вернул пользователю: {username} деньги по причине: {error}'))
                        else:
                            send_error_with_inline_url(c, USER_ID, orderID, error)
                        logger.error(f"[AUTO_STARS] Критическая ошибка: {error} (orderID={orderID})")
                        deactivate_all_lots(c, SUBCATEGORY_ID)
                        return

                found_success = False
                check_error = None
                for attempt in range(25):
                    try:
                        with httpx.Client() as client:
                            rq = client.get(
                                f'https://preview.toncenter.com/api/v3/traces?msg_hash={tx_hash}&include_actions=true')
                        response_data = rq.json()

                        for trace in response_data.get('traces', []):
                            for action in trace.get('actions', []):
                                success = action.get('success', False)
                                if success:
                                    logger.info(f"Транзакция с хешем {action['trace_external_hash']} успешна.")
                                    found_success = True
                                    break
                            if found_success:
                                break

                        if found_success:
                            break
                        else:
                            logger.warning(f"Попытка {attempt + 1}: транзакция не найдена или неуспешна.")
                            await asyncio.sleep(5)
                    except Exception as e:
                        logger.error(f"Ошибка при проверке транзакции (попытка {attempt + 1}): {e}")
                        check_error = str(e)
                        await asyncio.sleep(5)

                if not found_success:
                    check_error = check_error or "Не удалось получить подтверждение транзакции после 15 попыток."
                    logger.error(check_error)
                    update_stats(False, stars_quantity)
                    # Покупателю — только универсальное сообщение
                    c.send_message(buyer_chat_id, sanitize_telegram_text(
                        "❌ Ваш заказ не выполнен. Деньги возвращены. Пожалуйста, свяжитесь с поддержкой."))
                    if config["AUTO_REFUND"]:
                        c.account.refund(orderID)
                        c.telegram.bot.send_message(USER_ID, sanitize_telegram_text(
                            f'Вернул пользователю: {username} деньги по причине: {check_error}'))
                    else:
                        c.telegram.bot.send_message(USER_ID, sanitize_telegram_text(
                            f"У вас произошла ошибка с пользователем: https://funpay.com/orders/{orderID}/\nОшибка: {check_error}\nПросьба вернуть средства"))
                    logger.error(f"[AUTO_STARS] Критическая ошибка: {check_error} (orderID={orderID})")
                    deactivate_all_lots(c, SUBCATEGORY_ID)
                    return

                logger.info(f"Платёж успешен для {username}: TX Hash: {tx_hash}, Ref ID: {ref_id}, Qty: {quantity}")
                update_stats(True, stars_quantity)
                try:
                    c.send_message(
                        buyer_chat_id,
                        sanitize_telegram_text(f"""
🌟 Успешная сделка!
👤 Покупатель: {username}
⭐️ Stars: {quantity}
🔑 Ref ID: Ref#{ref_id}
✅ Статус: Готово

🔗 Доп подробности: {tx_hash}


📝 Оставьте отзыв — это мотивирует! 😎
                        """)
                    )
                except Exception as e:
                    logger.error(f"[AUTO_STARS] Ошибка при отправке сообщения клиенту: {e}")
                try:
                    c.telegram.bot.send_message(
                        USER_ID,
                        sanitize_telegram_text(f"""
🌟 Транзакция успешно завершена!
🔗 Подробности: https://preview.toncenter.com/api/v3/traces?msg_hash={tx_hash}&include_actions=true
🔗 Доп подробности: https://tonviewer.com/transaction/{tx_hash}
👤 Покупатель: {username}
⭐️ Stars: {quantity}
🔑 Ref ID: Ref#{ref_id}
✅ Статус: Готово

📝 Поделитесь впечатлениями, буду рад! 😇
                        """),
                        parse_mode="HTML"
                    )
                except Exception as e:
                    logger.error(f"[AUTO_STARS] Ошибка при отправке сообщения админу: {e}")
                orders = orders_info.get(buyer_chat_id, [])
                for order in orders:
                    if order['orderID'] == orderID and not order.get('completed', False):
                        order['completed'] = True
                        break
                return

            except Exception as e:
                logger.error(f"Ошибка при обработке платежа для {username}: {e}")
                try:
                    # Покупателю — только универсальное сообщение
                    c.send_message(buyer_chat_id,
                                   sanitize_telegram_text(f"❌ Ваш заказ не выполнен. Деньги возвращены. Пожалуйста, свяжитесь с поддержкой."))
                except Exception as send_error:
                    logger.error(f"Не удалось отправить сообщение об ошибке пользователю {buyer_chat_id}: {send_error}")
                logger.error(f"[AUTO_STARS] Критическая ошибка: {e} (orderID={orderID})")
                deactivate_all_lots(c, SUBCATEGORY_ID)
                break

        logger.error(f"Превышено количество попыток ({max_retries}) для заказа {orderID}.")
        update_stats(False, stars_quantity)
        # Покупателю — только универсальное сообщение
        c.send_message(buyer_chat_id, sanitize_telegram_text(
            "❌ Не удалось выполнить транзакцию после нескольких попыток. Деньги возвращены. Пожалуйста, свяжитесь с поддержкой."))
        if config["AUTO_REFUND"]:
            c.account.refund(orderID)
            c.telegram.bot.send_message(USER_ID, sanitize_telegram_text(
                f'Вернул пользователю: {username} деньги по причине: Превышено количество попыток'))
        else:
            send_error_with_inline_url(c, USER_ID, orderID, "Превышено количество попыток выполнения транзакции")
        logger.error(f"[AUTO_STARS] Критическая ошибка: Превышено количество попыток (orderID={orderID})")
        deactivate_all_lots(c, SUBCATEGORY_ID)


payment_processor: "PaymentProcessor | None" = None


class PluginFilter(Filter):
    def filter(self, record):
        return record.name == "FPC.autostars"


file_handler = logging.FileHandler("auto.log")
file_handler.setLevel(logging.DEBUG)
file_handler.addFilter(PluginFilter())
formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)
stream_handler = logging.StreamHandler()
stream_handler.setLevel(logging.DEBUG)
stream_handler.setFormatter(formatter)
logger.addHandler(stream_handler)

LOGGER_PREFIX = "[AUTO autostars]"
UPDATE = """
- Обработка 406 ошибки
- Не просит @username, при ошибке json передачи

"""

NAME = "AutoStars"
VERSION = "4.0"
DESCRIPTION = "Плагин для авто-накрутки Stars через Fragment."
CREDITS = "@AnastasiaPisun"
UUID = "f3a1c2d4-8b7e-4f9a-b3c1-2d4e6f8a0b1c"
SETTINGS_PAGE = False

RUNNING = True
chat_id = None


def handle_new_order_stars(c: Cardinal, e: NewOrderEvent, *args):
    global RUNNING, chat_id, orders_info
    if not RUNNING:
        return
    OrderID = e.order.id
    buyer_chat_id_e = e.order.buyer_id

    logger.debug(f"Получен новый заказ #{OrderID}")
    logger.debug(f"Покупатель: {e.order.buyer_username} (ID: {e.order.buyer_id})")
    logger.debug(f"Описание: {e.order.description}")
    logger.debug(f"Сумма: {e.order.price} {e.order.currency}")
    logger.debug(f"Количество: {e.order.amount}")

    username_from_order = None
    need_to_ask_username = True

    try:
        order_details = c.account.get_order(OrderID)
        if order_details:
            logger.debug(f"Подробная информация о заказе #{OrderID}:")
            logger.debug(f"Статус заказа: {order_details.status}")

            logger.debug(f"Параметры лота:")
            for param_name, param_value in order_details.lot_params:
                logger.debug(f"  - {param_name}: {param_value}")

            logger.debug(f"Параметры покупателя:")
            for param_name, param_value in order_details.lot_params_dict.items():
                logger.debug(f"  - {param_name}: {param_value}")

                if param_name == "Telegram Username" and param_value:
                    logger.debug(f"Найден Telegram Username в параметрах: {param_value}")

                    username_value = param_value.strip()

                    t_me_match = re.search(r't\.me/(\w+)', username_value.lower())
                    if t_me_match:
                        extracted_username = t_me_match.group(1)
                        logger.debug(f"Извлечен username из ссылки t.me: {extracted_username}")
                        username_value = extracted_username
                        has_links = False
                    else:
                        has_links = any(link in username_value.lower() for link in ["http://", "https://", "t.me/"])

                    if not has_links and username_value:
                        if not username_value.startswith('@'):
                            username_value = '@' + username_value

                        username_from_order = username_value
                        need_to_ask_username = False
                        logger.debug(f"Автоматически установлен Telegram Username: {username_from_order}")

            if order_details.character_name:
                logger.debug(f"Имя персонажа: {order_details.character_name}")
    except Exception as e:
        logger.error(f"Ошибка при получении расширенных данных заказа: {e}")

    match = re.search(r'(\d+)\s*звёзд?', e.order.description, re.IGNORECASE)
    if match:
        stars_count = int(match.group(1))
        if e.order.amount >= 1:
            total_stars = stars_count * e.order.amount
            c.send_message(
                buyer_chat_id_e,
                sanitize_telegram_text(f"Вы приобрели {e.order.amount} лотов, общее количество Stars: {total_stars}.")
            )
            ntfc_new_order = (
                "💰 <b>Новый заказ:</b> <code>{}</code>\n\n"
                "<b><i>🙍‍♂️ Покупатель:</i></b>  <code>{}</code>\n"
                "<b><i>💵 Сумма:</i></b>  <code>{}</code>\n"
                "<b><i>📇 ID:</i></b> <code>#{}</code>\n\n"
                "<i>{}</i>"
            )
            delivery_info = f"Автовыдача {total_stars} Stars активирована."
            notification_text = ntfc_new_order.format(
                e.order.description,
                e.order.buyer_username,
                f"{e.order.price} {e.order.currency}",
                e.order.id,
                delivery_info
            )
            try:
                buyer_chat = c.account.get_chat_by_name(e.order.buyer_username, True)
                if buyer_chat is None:
                    raise AttributeError
                buyer_chat_id = buyer_chat.id
            except AttributeError:
                return

            if buyer_chat_id not in orders_info:
                orders_info[buyer_chat_id] = []

            order_info = {
                "username": username_from_order,
                "confirmed": False,
                "auto_username": not need_to_ask_username,
                "completed": False,
                "orderID": OrderID,
                "stars_count": total_stars
            }

            orders_info[buyer_chat_id].append(order_info)

            if not need_to_ask_username:
                fragment_found_name = None
                fragment_id = None
                try:
                    search_payload = {
                        "query": username_from_order.replace("@", ""),
                        "quantity": 50,
                        "method": "searchStarsRecipient"
                    }
                    response_search = requests.post(url, headers=headers, data=search_payload)
                    response_search.raise_for_status()
                    data_search = response_search.json()
                    if data_search.get('ok'):
                        fragment_found_name = data_search.get('found', {}).get('name')
                        fragment_id = data_search.get('found', {}).get('recipient')
                except Exception as err:
                    logger.error(f"Ошибка при проверке username: {err}")

                order_info['fragment_found_name'] = fragment_found_name
                order_info['fragment_id'] = fragment_id

                blurred_name = ''
                if fragment_found_name:
                    for i in range(len(fragment_found_name)):
                        blurred_name += fragment_found_name[i] if i % 2 == 0 else '*'
                else:
                    blurred_name = 'Не найдено'

                fragment_display = fragment_id if fragment_id else "Не найдено"
                additional_info = f"\nИмя пользователя (найдено в телеграмме): {blurred_name}\nFragment ID: {fragment_display}"

                c.send_message(
                    buyer_chat_id,
                    sanitize_telegram_text(
                        f"✨ ЗАКАЗ НА {total_stars} STARS ПРИНЯТ! ✨\n"
                        f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
                        f"👤 Обнаружен никнейм: {username_from_order}\n"
                        f"📝 Данные Fragment: {additional_info}\n\n"
                        f"📋 ИНСТРУКЦИИ:\n"
                        f"✅ Для подтверждения: 'Да'\n"
                        f"❌ Для изменения: 'Нет'\n"
                        f"🔄 Для возврата: '!бэк'\n\n"
                        f"━━━━━━━━━━━━━━━━━━━━━━"
                    )
                )
                logger.info(
                    f"Автоматически найден username: {username_from_order}, Fragment Name: {blurred_name}, Fragment ID: {fragment_display}"
                )
            else:
                c.send_message(
                    buyer_chat_id,
                    sanitize_telegram_text(
                        f"⭐️ ЗАКАЗ НА {total_stars} STARS ПРИНЯТ! ⭐️\n"
                        f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
                        f"❗️ НЕОБХОДИМО УКАЗАТЬ ВАШ НИКНЕЙМ\n\n"
                        f"👉 Введите ваш @username для получения Stars\n"
                        f"👉 Проверьте профиль: Настройки → Изменить профиль\n\n"
                        f"⚠️ Без @username пополнение невозможно!\n\n"
                        f"❌ Для отмены и возврата: '!бэк'\n"
                        f"━━━━━━━━━━━━━━━━━━━━━━"
                    )
                )
        else:
            c.send_message(
                buyer_chat_id_e,
                sanitize_telegram_text(f"Заказ на {stars_count} Stars")
            )


def handle_new_message_text(c: Cardinal, e: NewMessageEvent, *args):
    global RUNNING, chat_id, orders_info
    if not RUNNING:
        return
    buyer_chat_id = e.message.chat_id
    my_user = c.account.username
    my_id = c.account.id

    if buyer_chat_id == my_id:
        return
    if e.message.text.strip().lower().startswith("!status"):
        handle_status_command(c, e)
        return
    if e.message.author.lower() in ["funpay", my_user.lower()]:
        return
    if buyer_chat_id not in orders_info or not orders_info[buyer_chat_id]:
        return
    current_order = next((o for o in reversed(orders_info[buyer_chat_id]) if not o.get('completed', False)), None)
    if current_order is None:
        return

    if e.message.text.strip().lower().startswith("!бэк"):
        if current_order.get('completed', False) or current_order.get('is_canceled', False) or current_order.get(
                'answered', False):
            return
        c.account.refund(current_order['orderID'])
        current_order['is_canceled'] = True
        c.send_message(
            buyer_chat_id,
            sanitize_telegram_text(
                "❌ Заказ отменен, средства возвращены. Вы не можете возобновить этот заказ. Для нового заказа оформите оплату заново.")
        )
        return

    if current_order.get('is_canceled', False):
        return

    if current_order.get('username') is not None and current_order.get('auto_username',
                                                                       False) and not current_order.get('confirmed',
                                                                                                        False):
        user_response = e.message.text.strip().lower()

        if user_response in ['да', '+', 'yes', 'y', 'д']:
            current_order['confirmed'] = True
            current_order['answered'] = True
            orderID = current_order['orderID']
            stars_quantity = current_order.get('stars_count', 50)
            username = current_order['username']

            if payment_processor is not None:
                payment_processor.enqueue_payment(
                    c, buyer_chat_id, username, stars_quantity, orderID
                )

            current_order['answered'] = True
            current_order['auto_username'] = False
            current_order['username'] = None

            c.send_message(
                buyer_chat_id,
                sanitize_telegram_text("Пожалуйста, введите верный @username.")
            )

        return

    if current_order['username'] is None:
        if not re.match(r'^@\w+$', e.message.text.strip()):
            c.send_message(
                e.message.chat_id,
                sanitize_telegram_text("❌ Неверный формат username. Пожалуйста, введите @username.")
            )
            return
        username = e.message.text.strip()
        current_order['username'] = username
        current_order['confirmed'] = False
        fragment_found_name = None
        fragment_id = None
        try:
            search_payload = {
                "query": username.replace("@", ""),
                "quantity": 50,
                "method": "searchStarsRecipient"
            }
            response_search = requests.post(url, headers=headers, data=search_payload)
            response_search.raise_for_status()
            data_search = response_search.json()
            if data_search.get('ok'):
                fragment_found_name = data_search.get('found', {}).get('name')
                fragment_id = data_search.get('found', {}).get('recipient')
        except Exception as _search_err:
            logger.warning(f"Ошибка при поиске username в Fragment: {_search_err}")
        current_order['fragment_found_name'] = fragment_found_name
        current_order['fragment_id'] = fragment_id

        blurred_name = ''
        if fragment_found_name:
            for i in range(len(fragment_found_name)):
                blurred_name += fragment_found_name[i] if i % 2 == 0 else '*'
        else:
            blurred_name = 'Не найдено'

        fragment_display = fragment_id if fragment_id else "Не найдено"
        additional_info = f"\nИмя пользователя (найдено в телеграмме): {blurred_name}\nFragment ID: {fragment_display}"
        c.send_message(
            e.message.chat_id,
            sanitize_telegram_text(
                f"🤖 Ваш никнейм в Telegram: {username} | {additional_info} \n"
                "Если информация верна, введите '+' или 'Да'. Если хотите изменить никнейм, напишите '-' или 'Нет'. Для возврата средств введите '!бэк'.\n\nПочему ник в блюре? Чтобы площадка FunPay не выдала блокировку из-за вашего name"
            )
        )
        logger.info(
            f"Найден username: {username}, Fragment Name: {blurred_name}, Fragment ID: {fragment_display}"
        )
        return

    if current_order['username'] is not None and not current_order['confirmed']:
        user_response = e.message.text.strip().lower()
        if user_response in ['да', '+', 'yes', 'y', 'д']:
            current_order['confirmed'] = True
            current_order['answered'] = True
            orderID = current_order['orderID']
            stars_quantity = current_order.get('stars_count', 50)
            if payment_processor is not None:
                payment_processor.enqueue_payment(
                    c, buyer_chat_id, current_order['username'], stars_quantity, orderID
                )

        elif user_response in ['нет', '-', 'no', 'n', 'н']:
            current_order['answered'] = True
            current_order['username'] = None
            c.send_message(
                e.message.chat_id,
                sanitize_telegram_text("Пожалуйста, введите @username ещё раз.")
            )
        else:
            c.send_message(
                e.message.chat_id,
                sanitize_telegram_text("Пожалуйста, ответьте '+', 'Да', '-' или 'Нет'.")
            )


def stars_auto(c: Cardinal, e, *args):
    if isinstance(e, NewOrderEvent):
        handle_new_order_stars(c, e, *args)
    elif isinstance(e, NewMessageEvent):
        handle_new_message_text(c, e, *args)


def activate_lots(c: Cardinal, chat_id: int):
    json_path = 'storage/cache/auto_stars_id.json'
    if not os.path.exists(json_path):
        logger.error(f"Файл {json_path} не найден.")
        c.send_message(chat_id, sanitize_telegram_text(f"❌ Файл {json_path} не найден."))
        return
    try:
        with open(json_path, 'r', encoding='utf-8') as file:
            lot_ids: List[int] = json.load(file)
        logger.debug(f"Загруженные ID лотов: {lot_ids}")
    except json.JSONDecodeError as e:
        logger.error(f"Ошибка декодирования JSON из файла {json_path}: {e}")
        c.send_message(chat_id, sanitize_telegram_text(f"❌ Ошибка декодирования JSON: {e}"))
        return
    except Exception as e:
        logger.error(f"Не удалось прочитать файл {json_path}: {e}")
        c.send_message(chat_id, sanitize_telegram_text(f"❌ Не удалось прочитать файл: {e}"))
        return
    if not isinstance(lot_ids, list):
        logger.error(f"Неверный формат данных в {json_path}. Ожидался список ID.")
        c.send_message(chat_id, sanitize_telegram_text("❌ Неверный формат JSON."))
        return
    activated_lots = []
    already_active = []
    not_found = []
    invalid_ids = []
    errors = []
    rate_limited = False

    for lot_id in lot_ids:
        if rate_limited:
            break

        if not isinstance(lot_id, int):
            invalid_ids.append(lot_id)
            continue
        try:
            fields = c.account.get_lot_fields(lot_id)
            if fields is None:
                not_found.append(lot_id)
                continue
            if fields.active:
                already_active.append(lot_id)
                continue
            fields.active = True
            c.account.save_lot(fields)
            activated_lots.append(lot_id)
            # Добавляем небольшую задержку между запросами
            time.sleep(1)
        except FunPayAPI.common.exceptions.RequestFailedError as e:
            if '429' in str(e):
                logger.warning(f"Достигнут лимит запросов к FunPay API (429) при активации лота {lot_id}")
                errors.append((lot_id, "Превышен лимит запросов (429)"))
                rate_limited = True
            else:
                errors.append((lot_id, str(e)))
        except Exception as e:
            errors.append((lot_id, str(e)))

    report = "✅ **Активация лотов завершена.**\n\n"
    if activated_lots:
        report += f"**Активированы**: {', '.join(map(str, activated_lots))}\n"
    if already_active:
        report += f"**Уже активны**: {', '.join(map(str, already_active))}\n"
    if not_found:
        report += f"**Не найдены**: {', '.join(map(str, not_found))}\n"
    if invalid_ids:
        report += f"**Неверные ID**: {', '.join(map(str, invalid_ids))}\n"
    if errors:
        error_details = "; ".join([f"{lot_id}: {err}" for lot_id, err in errors])
        report += f"**Ошибки**: {error_details}\n"
    if rate_limited:
        report += "\n⚠️ **Внимание**: Активация была прервана из-за превышения лимита запросов FunPay. Повторите попытку через несколько минут."

    c.telegram.bot.send_message(chat_id, sanitize_telegram_text(report))


def deactivate_lots(c: Cardinal, chat_id: int):
    c.update_lots_and_categories()
    try:
        subcategory = c.account.get_subcategory(FunPayAPI.types.SubCategoryTypes.COMMON, SUBCATEGORY_ID)
        my_lots = c.tg_profile.get_sorted_lots(2).get(subcategory, {})
    except Exception as e:
        c.send_message(chat_id, sanitize_telegram_text(f"❌ Ошибка получения лотов: {e}"))
        return
    if not my_lots:
        c.send_message(chat_id, sanitize_telegram_text("ℹ️ Нет лотов для деактивации."))
        return
    deactivated_lots = []
    already_inactive = []
    errors = []
    not_found = []
    rate_limited = False

    for lot_id, lot in my_lots.items():
        if rate_limited:
            break

        if not isinstance(lot_id, int):
            continue
        try:
            fields = c.account.get_lot_fields(lot_id)
            if fields is None:
                not_found.append(lot_id)
                continue
            if not fields.active:
                already_inactive.append(lot_id)
                continue
            fields.active = False
            c.account.save_lot(fields)
            deactivated_lots.append(lot_id)
            # Увеличиваем задержку между запросами
            time.sleep(2)
        except FunPayAPI.common.exceptions.RequestFailedError as e:
            if '429' in str(e):
                logger.warning(f"Достигнут лимит запросов к FunPay API (429) при деактивации лота {lot_id}")
                errors.append((lot_id, "Превышен лимит запросов (429)"))
                rate_limited = True
            else:
                errors.append((lot_id, str(e)))
        except Exception as e:
            errors.append((lot_id, str(e)))

    report = "✅ **Деактивация лотов завершена.**\n\n"
    if deactivated_lots:
        report += f"**Деактивированы**: {', '.join(map(str, deactivated_lots))}\n"
    if already_inactive:
        report += f"**Уже были неактивны**: {', '.join(map(str, already_inactive))}\n"
    if not_found:
        report += f"**Не найдены**: {', '.join(map(str, not_found))}\n"
    if errors:
        error_details = "; ".join([f"{lot_id}: {err}" for lot_id, err in errors])
        report += f"**Ошибки**: {error_details}\n"
    if rate_limited:
        report += "\n⚠️ **Внимание**: Деактивация была прервана из-за превышения лимита запросов FunPay. Повторите попытку через несколько минут."

    c.telegram.bot.send_message(USER_ID, sanitize_telegram_text(report))


def deactivate_all_lots(c, subcategory_id):
    """Деактивирует все лоты в указанной подкатегории и логирует результат."""
    try:
        c.update_lots_and_categories()
        subcategory = c.account.get_subcategory(FunPayAPI.types.SubCategoryTypes.COMMON, subcategory_id)
        my_lots = c.tg_profile.get_sorted_lots(2).get(subcategory, {})
        deactivated = 0
        for lot_id, lot in my_lots.items():
            try:
                fields = c.account.get_lot_fields(lot_id)
                if fields and fields.active:
                    fields.active = False
                    c.account.save_lot(fields)
                    deactivated += 1
                    logger.debug(f"Лот {lot_id} деактивирован из-за недостатка средств.")
                    c.telegram.bot.send_message(USER_ID, sanitize_telegram_text(f"❌ Лот {lot_id} деактивирован из-за недостатка средств."))
            except Exception as e:
                logger.error(f"Ошибка при деактивации лота {lot_id}: {e}")
        if deactivated == 0:
            logger.warning("Не удалось деактивировать ни одного лота! Проверьте subcategory и список лотов.")
    except Exception as e:
        logger.error(f"Глобальная ошибка при деактивации лотов: {e}")


def stars(m: types.Message, c: Cardinal):
    global RUNNING
    if RUNNING:
        c.telegram.bot.send_message(
            m.chat.id,
            sanitize_telegram_text("🚨 Автопродажа TG STARS уже включена.")
        )
        return
    if payment_processor is None:
        c.telegram.bot.send_message(m.chat.id, sanitize_telegram_text("❌ PaymentProcessor не инициализирован. Перезапустите Cardinal."))
        return
    RUNNING = True
    future = asyncio.run_coroutine_threadsafe(check_wallet_balance(), payment_processor.loop)
    try:
        balance_ton = future.result(timeout=10)
    except Exception as e:
        c.telegram.bot.send_message(m.chat.id, sanitize_telegram_text("❌ Не удалось проверить баланс кошелька."))
        RUNNING = False
        return
    c.telegram.bot.send_message(
        m.chat.id,
        sanitize_telegram_text(f"🚀 Автопродажа TG STARS активирована. Баланс кошелька: {balance_ton} TON.")
    )


def off_stars(m: types.Message, c: Cardinal):
    global RUNNING
    if not RUNNING:
        c.telegram.bot.send_message(
            m.chat.id,
            sanitize_telegram_text("🛑 Автопродажа TG STARS уже отключена!")
        )
        return
    RUNNING = False
    c.telegram.bot.send_message(
        m.chat.id,
        sanitize_telegram_text("🛑 Автопродажа TG STARS отключена.")
    )


async def get_wallet_balance():
    try:
        balance_nano = await check_wallet_balance()
        if config["USE_OLD_BALANCE"]:
            return f"{balance_nano} (старый формат)"
        else:
            balance_ton = balance_nano / 1_000_000_000
            return f"{balance_ton:.2f} TON"
    except Exception as e:
        logger.error(f"Ошибка при получении баланса: {e}")
        return "Неизвестно"


def stars_config(c: Cardinal, m: types.Message):
    """Инициализация панели управления /stars_config с балансом и кнопкой статистики."""
    try:
        c.update_lots_and_categories()
        subcategory = c.account.get_subcategory(FunPayAPI.types.SubCategoryTypes.COMMON, SUBCATEGORY_ID)
        my_lots = c.tg_profile.get_sorted_lots(2).get(subcategory, {})

        active_lots = []
        try:
            for lot_id, lot in my_lots.items():
                try:
                    lot_fields = c.account.get_lot_fields(lot_id)
                    if lot_fields and lot_fields.active:
                        active_lots.append(lot_id)
                except FunPayAPI.common.exceptions.RequestFailedError as lot_err:
                    if '429' in str(lot_err):
                        logger.warning(f"Достигнут лимит запросов к FunPay API (429) при проверке лота {lot_id}")
                    else:
                        logger.error(f"Ошибка при получении данных лота {lot_id}: {lot_err}")
        except Exception as lots_err:
            logger.error(f"Ошибка при обработке лотов: {lots_err}")

        balance_text = "Недоступно"
        if payment_processor is not None:
            try:
                balance_future = asyncio.run_coroutine_threadsafe(get_wallet_balance(), payment_processor.loop)
                balance_text = balance_future.result(timeout=10)
            except Exception as _bal_err:
                logger.error(f"Ошибка получения баланса: {_bal_err}")

        activation_status = "🟢 Активирован"

        keyboard = InlineKeyboardMarkup(row_width=2)
        status_btn = InlineKeyboardButton(
            text=f"{'🟢 Вкл' if RUNNING else '🔴 Выкл'}",
            callback_data="toggle_autosale"
        )
        lots_btn = InlineKeyboardButton(
            text=f"{'⚡️ Лоты: Вкл' if active_lots else '💤 Лоты: Выкл'}",
            callback_data="toggle_lots"
        )
        logs_btn = InlineKeyboardButton(text="📋 Логи", callback_data="send_logs")
        settings_btn = InlineKeyboardButton(text="⚙️ Настройки", callback_data="open_settings")
        stats_btn = InlineKeyboardButton(text="📊 Статистика", callback_data="daily_stats")
        keyboard.add(status_btn, lots_btn)
        keyboard.add(logs_btn, settings_btn)
        keyboard.add(stats_btn)

        status_text = "🟢 Активна" if RUNNING else "🔴 Неактивна"
        lots_text = f"⚡️ Активных: {len(active_lots)}" if active_lots else "💤 Нет активных"
        message_text = (
            "✨ <b>AutoStars: Панель управления</b> ✨\n"
            "────────────────────\n"
            f"<b>Активация:</b> {activation_status}\n"
            f"<b>Статус:</b> {status_text}\n"
            f"<b>Лоты:</b> {lots_text}\n"
            f"<b>💰 Баланс:</b> {balance_text}\n\n"
            "💡 <b>Проблемы с отображением баланса?</b>\n"
            "Если баланс отображается некорректно (например, 2.35e-10 TON), переключите формат баланса:\n"
            "⚙️ Настройки → 💰 Баланс → выберите 'Старый формат'.\n"
            "Если проблема не решена, проверьте seed-фразу в настройках.\n\n"
            "────────────────────\n"
            "Выберите действие ниже:"
        )

        c.telegram.bot.send_message(
            chat_id=m.chat.id,
            text=message_text,
            reply_markup=keyboard,
            parse_mode="HTML"
        )
    except Exception as e:
        error_message = sanitize_telegram_text(str(e))
        if len(error_message) > 200:
            error_message = error_message[:197] + "..."
        c.telegram.bot.send_message(
            m.chat.id,
            f"❌ Ошибка при загрузке панели: {error_message}"
        )
        logger.error(f"Ошибка в stars_config: {e}")


def update_config_panel(c: Cardinal, chat_id: int, message_id: int):
    try:
        c.update_lots_and_categories()
        subcategory = c.account.get_subcategory(FunPayAPI.types.SubCategoryTypes.COMMON, SUBCATEGORY_ID)
        my_lots = c.tg_profile.get_sorted_lots(2).get(subcategory, {})

        active_lots = []
        try:
            for lot_id, lot in my_lots.items():
                try:
                    lot_fields = c.account.get_lot_fields(lot_id)
                    if lot_fields and lot_fields.active:
                        active_lots.append(lot_id)
                except FunPayAPI.common.exceptions.RequestFailedError as lot_err:
                    if '429' in str(lot_err):
                        logger.warning(f"Достигнут лимит запросов к FunPay API (429) при проверке лота {lot_id}")
                    else:
                        logger.error(f"Ошибка при получении данных лота {lot_id}: {lot_err}")
        except Exception as lots_err:
            logger.error(f"Ошибка при обработке лотов: {lots_err}")

        balance_text = "Недоступно"
        if payment_processor is not None:
            try:
                balance_future = asyncio.run_coroutine_threadsafe(get_wallet_balance(), payment_processor.loop)
                balance_text = balance_future.result(timeout=10)
            except Exception as _bal_err:
                logger.error(f"Ошибка получения баланса: {_bal_err}")

        activation_status = "🟢 Активирован"

        keyboard = InlineKeyboardMarkup(row_width=2)
        status_btn = InlineKeyboardButton(
            text=f"{'🟢 Вкл' if RUNNING else '🔴 Выкл'}",
            callback_data="toggle_autosale"
        )
        lots_btn = InlineKeyboardButton(
            text=f"{'⚡️ Лоты: Вкл' if active_lots else '💤 Лоты: Выкл'}",
            callback_data="toggle_lots"
        )
        logs_btn = InlineKeyboardButton(text="📋 Логи", callback_data="send_logs")
        settings_btn = InlineKeyboardButton(text="⚙️ Настройки", callback_data="open_settings")
        stats_btn = InlineKeyboardButton(text="📊 Статистика", callback_data="daily_stats")
        keyboard.add(status_btn, lots_btn)
        keyboard.add(logs_btn, settings_btn)
        keyboard.add(stats_btn)

        status_text = "🟢 Активна" if RUNNING else "🔴 Неактивна"
        lots_text = f"⚡️ Активных: {len(active_lots)}" if active_lots else "💤 Нет активных"
        message_text = (
            "✨ <b>AutoStars: Панель управления</b> ✨\n"
            "────────────────────\n"
            f"<b>Активация:</b> {activation_status}\n"
            f"<b>Статус:</b> {status_text}\n"
            f"<b>Лоты:</b> {lots_text}\n"
            f"<b>💰 Баланс:</b> {balance_text}\n"
            "────────────────────\n"
            "Выберите действие ниже:"
        )

        c.telegram.bot.edit_message_text(
            chat_id=chat_id,
            message_id=message_id,
            text=message_text,
            reply_markup=keyboard,
            parse_mode="HTML"
        )
    except Exception as e:
        error_message = sanitize_telegram_text(str(e))
        if len(error_message) > 200:
            error_message = error_message[:197] + "..."
        c.telegram.bot.send_message(
            chat_id,
            f"❌ Ошибка при обновлении панели: {error_message}"
        )
        logger.error(f"Ошибка в update_config_panel: {e}")


def update_settings_panel(c: Cardinal, chat_id: int, message_id: int):
    """Обновление панели настроек с кнопками для изменения параметров."""
    keyboard = InlineKeyboardMarkup(row_width=1)
    keyboard.add(
        InlineKeyboardButton(text="🔑 Хэш", callback_data="edit_hash"),
        InlineKeyboardButton(text="🍪 Куки", callback_data="edit_cookie"),
        InlineKeyboardButton(text="🔐 Мнемоника", callback_data="edit_mnemonic"),
        InlineKeyboardButton(text="👤 User ID", callback_data="edit_user_id"),
        InlineKeyboardButton(text="💳 Адрес кошелька", callback_data="show_wallet_address"),
        InlineKeyboardButton(
            text=f"🤖 Возврат: {'Авто' if config['AUTO_REFUND'] else 'Ручной'}",
            callback_data="toggle_refund"
        ),
        InlineKeyboardButton(
            text=f"👻 Отправка: {'Анонимная' if config['SHOW_SENDER'] == '0' else 'Не анонимная'}",
            callback_data="toggle_sender"
        ),
        InlineKeyboardButton(
            text=f"💰 Баланс: {'Старый формат' if config['USE_OLD_BALANCE'] else 'Новый формат'}",
            callback_data="toggle_balance_format"
        ),
        InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_main")
    )
    message_text = (
        "⚙️ <b>Настройки AutoStars</b>\n"
        "────────────────────\n"
        "Выберите параметр для изменения:"
    )
    c.telegram.bot.edit_message_text(
        chat_id=chat_id,
        message_id=message_id,
        text=message_text,
        reply_markup=keyboard,
        parse_mode="HTML"
    )


def get_daily_stats():
    """Получение ежедневной статистики по транзакциям в виде чистого текста."""
    date_str = datetime.datetime.now().strftime("%Y-%m-%d")
    day_stats = stats_data.get(date_str, {})

    if not day_stats:
        return None

    successful = day_stats.get("successful_transactions", 0)
    unsuccessful = day_stats.get("unsuccessful_transactions", 0)
    quantities = day_stats.get("quantities_sold", {})
    total_stars = sum(int(q) * count for q, count in quantities.items())

    quantities_text = "\n".join(
        [f"  - {q} Stars: {count} шт." for q, count in quantities.items()]) if quantities else "  - Нет данных"

    stats_message = (
        f"✨ Статистика за {date_str} ✨\n"
        "────────────────────\n"
        f"✅ Успешных транзакций: {successful}\n"
        f"❌ Неуспешных транзакций: {unsuccessful}\n"
        f"⭐️ Проданные Stars:\n{quantities_text}\n"
        f"💫 Всего продано: {total_stars} Stars\n"
        "────────────────────"
    )
    return stats_message


def handle_status_command(c: Cardinal, e: NewMessageEvent):
    """Обработка команды !status для получения статистики."""
    text = e.message.text.strip()
    parts = text.split(" ", 1)
    if len(parts) > 1 and parts[1].strip():
        date_str = parts[1].strip()
    else:
        date_str = datetime.datetime.now().strftime("%Y-%m-%d")

    if date_str not in stats_data:
        msg = (
            f"Статистика за {date_str} отсутствует.\n"
            "Вероятно, не было транзакций или дата указана неверно."
        )
        c.send_message(e.message.chat_id, msg)
        return

    image_stream = generate_order_graph(date_str)
    if image_stream is None:
        c.send_message(e.message.chat_id, "Статистика за эту дату отсутствует.")
        return

    c.account.send_image(
        e.message.chat_id,
        image_stream,
        chat_name=e.message.chat_name
    )


def init_commands(c: Cardinal):
    """Инициализация команд и callback-обработчиков для бота."""
    global payment_processor
    if payment_processor is None:
        try:
            payment_processor = PaymentProcessor()
            logger.info("[AutoStars] PaymentProcessor успешно инициализирован.")
        except Exception as _pp_err:
            logger.error(f"[AutoStars] Не удалось инициализировать PaymentProcessor: {_pp_err}")

    c.add_telegram_commands(UUID, [
        ("stars_config", "настройка автопродажи тг старсов", True),
    ])
    c.telegram.msg_handler(lambda m: stars_config(c, m), commands=["stars_config"])

    @c.telegram.bot.callback_query_handler(func=lambda call: call.data in [
        "toggle_autosale", "toggle_lots", "send_logs", "open_settings", "edit_hash",
        "edit_cookie", "edit_mnemonic", "toggle_refund", "back_to_main", "cancel",
        "edit_user_id", "daily_stats", "toggle_sender", "toggle_balance_format",
        "show_wallet_address"
    ])
    def handle_config_callback(call):
        global RUNNING, SHOW_SENDER
        data = call.data
        chat_id = call.message.chat.id
        message_id = call.message.message_id
        callback_query_id = call.id

        try:
            c.telegram.bot.answer_callback_query(callback_query_id)
        except Exception:
            pass

        try:
            if data == "toggle_autosale":
                if RUNNING:
                    RUNNING = False
                    c.telegram.bot.send_message(
                        chat_id,
                        sanitize_telegram_text("🛑 Автопродажа отключена.")
                    )
                else:
                    if payment_processor is None:
                        c.telegram.bot.send_message(chat_id, sanitize_telegram_text("❌ PaymentProcessor не инициализирован. Перезапустите Cardinal."))
                        return
                    future = asyncio.run_coroutine_threadsafe(check_wallet_balance(), payment_processor.loop)
                    balance_ton = future.result(timeout=10)
                    RUNNING = True
                    c.telegram.bot.send_message(
                        chat_id,
                        sanitize_telegram_text(f"🚀 Автопродажа включена. Баланс: {balance_ton} TON")
                    )
                update_config_panel(c, chat_id, message_id)

            elif data == "toggle_lots":
                subcategory = c.account.get_subcategory(FunPayAPI.types.SubCategoryTypes.COMMON, SUBCATEGORY_ID)
                my_lots = c.tg_profile.get_sorted_lots(2).get(subcategory, {})
                active_lots = [lot_id for lot_id, lot in my_lots.items() if c.account.get_lot_fields(lot_id).active]
                if active_lots:
                    deactivate_lots(c, chat_id)
                else:
                    activate_lots(c, chat_id)
                time.sleep(1)
                update_config_panel(c, chat_id, message_id)

            elif data == "send_logs":
                log_file_path = "auto.log"
                if not os.path.exists(log_file_path):
                    c.telegram.bot.send_message(
                        chat_id,
                        sanitize_telegram_text("❌ Логи не найдены.")
                    )
                    return
                with open(log_file_path, 'rb') as log_file:
                    c.telegram.bot.send_document(
                        chat_id,
                        document=log_file,
                        caption="📋 Логи AutoStars"
                    )

            elif data == "open_settings":
                update_settings_panel(c, chat_id, message_id)

            elif data == "toggle_refund":
                config["AUTO_REFUND"] = not config["AUTO_REFUND"]
                with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
                    json.dump(config, f, indent=4, ensure_ascii=False)
                update_settings_panel(c, chat_id, message_id)

            elif data == "toggle_sender":
                config["SHOW_SENDER"] = "1" if config["SHOW_SENDER"] == "0" else "0"
                SHOW_SENDER = config["SHOW_SENDER"]
                with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
                    json.dump(config, f, indent=4, ensure_ascii=False)
                update_settings_panel(c, chat_id, message_id)

            elif data == "daily_stats":
                stats_message = get_daily_stats()
                if stats_message:
                    c.telegram.bot.send_message(
                        chat_id,
                        sanitize_telegram_text(stats_message),
                        parse_mode="HTML"
                    )
                else:
                    c.telegram.bot.send_message(
                        chat_id,
                        sanitize_telegram_text("📊 Статистика за сегодня отсутствует.")
                    )

            elif data == "edit_hash":
                current_hash = config.get("fragment_api", {}).get("hash", "Не задан")
                keyboard = InlineKeyboardMarkup(row_width=1)
                keyboard.add(InlineKeyboardButton(text="❌ Отмена", callback_data="cancel"))
                c.telegram.bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=message_id,
                    text=sanitize_telegram_text(f"🔑 Текущий хэш:\n{current_hash}\n\nВведите новый:"),
                    reply_markup=keyboard,
                    parse_mode="HTML"
                )

                def handle_new_hash(m):
                    global FRAGMENT_HASH, url, headers
                    if m.text.startswith('/'):
                        c.telegram.bot.send_message(chat_id, "❌ Ввод отменен.")
                        update_settings_panel(c, chat_id, message_id)
                        c.telegram.bot.remove_message_handler(handle_new_hash)
                        return
                    if m.text.lower() == "отмена":
                        update_settings_panel(c, chat_id, message_id)
                        c.telegram.bot.remove_message_handler(handle_new_hash)
                        return
                    config["fragment_api"]["hash"] = m.text.strip()
                    FRAGMENT_HASH = m.text.strip()
                    url = f"{FRAGMENT_URL}?hash={FRAGMENT_HASH}"
                    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
                        json.dump(config, f, indent=4, ensure_ascii=False)
                    c.telegram.bot.send_message(chat_id, "✅ Хэш обновлен!")
                    update_settings_panel(c, chat_id, message_id)
                    c.telegram.bot.remove_message_handler(handle_new_hash)

                c.telegram.bot.register_next_step_handler(call.message, handle_new_hash)

            elif data == "edit_cookie":
                current_cookie = config.get("fragment_api", {}).get("cookie", "Не задана")
                keyboard = InlineKeyboardMarkup(row_width=1)
                keyboard.add(InlineKeyboardButton(text="❌ Отмена", callback_data="cancel"))
                c.telegram.bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=message_id,
                    text=sanitize_telegram_text(f"🍪 Текущая куки:\n{current_cookie}\n\nВведите новую:"),
                    reply_markup=keyboard,
                    parse_mode="HTML"
                )

                def handle_new_cookie(m):
                    global FRAGMENT_COOKIE, headers
                    if m.text.startswith('/'):
                        c.telegram.bot.send_message(chat_id, "❌ Ввод отменен.")
                        update_settings_panel(c, chat_id, message_id)
                        c.telegram.bot.remove_message_handler(handle_new_cookie)
                        return
                    if m.text.lower() == "отмена":
                        update_settings_panel(c, chat_id, message_id)
                        c.telegram.bot.remove_message_handler(handle_new_cookie)
                        return
                    config["fragment_api"]["cookie"] = m.text.strip()
                    FRAGMENT_COOKIE = m.text.strip()
                    headers["Cookie"] = FRAGMENT_COOKIE
                    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
                        json.dump(config, f, indent=4, ensure_ascii=False)
                    c.telegram.bot.send_message(chat_id, "✅ Куки обновлена!")
                    update_settings_panel(c, chat_id, message_id)
                    c.telegram.bot.remove_message_handler(handle_new_cookie)

                c.telegram.bot.register_next_step_handler(call.message, handle_new_cookie)

            elif data == "edit_mnemonic":
                current_mnemonic = " ".join(config.get("MNEMONIC", []))
                keyboard = InlineKeyboardMarkup(row_width=1)
                keyboard.add(InlineKeyboardButton(text="❌ Отмена", callback_data="cancel"))
                c.telegram.bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=message_id,
                    text=sanitize_telegram_text(
                        f"🔐 Текущая мнемоника:\n{current_mnemonic}\n\nВведите новую (24 слова):"),
                    reply_markup=keyboard,
                    parse_mode="HTML"
                )

                def handle_new_mnemonic(m):
                    global MNEMONIC
                    if m.text.startswith('/'):
                        c.telegram.bot.send_message(chat_id, "❌ Ввод отменен.")
                        update_settings_panel(c, chat_id, message_id)
                        c.telegram.bot.remove_message_handler(handle_new_mnemonic)
                        return
                    if m.text.lower() == "отмена":
                        update_settings_panel(c, chat_id, message_id)
                        c.telegram.bot.remove_message_handler(handle_new_mnemonic)
                        return
                    new_mnemonic = m.text.strip().split()
                    if len(new_mnemonic) != 24:
                        c.telegram.bot.send_message(chat_id, "❌ Должно быть 24 слова!")
                        return
                    config["MNEMONIC"] = new_mnemonic
                    MNEMONIC = new_mnemonic
                    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
                        json.dump(config, f, indent=4, ensure_ascii=False)
                    c.telegram.bot.send_message(chat_id, "✅ Мнемоника обновлена!")
                    update_settings_panel(c, chat_id, message_id)
                    c.telegram.bot.remove_message_handler(handle_new_mnemonic)

                c.telegram.bot.register_next_step_handler(call.message, handle_new_mnemonic)

            elif data == "edit_user_id":
                current_user_id = config.get("user_id", "Не задан")
                keyboard = InlineKeyboardMarkup(row_width=1)
                keyboard.add(InlineKeyboardButton(text="❌ Отмена", callback_data="cancel"))
                c.telegram.bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=message_id,
                    text=sanitize_telegram_text(f"👤 Текущий User ID:\n{current_user_id}\n\nВведите новый:"),
                    reply_markup=keyboard,
                    parse_mode="HTML"
                )

                def handle_new_user_id(m):
                    global USER_ID
                    if m.text.startswith('/'):
                        c.telegram.bot.send_message(chat_id, "❌ Ввод отменен.")
                        update_settings_panel(c, chat_id, message_id)
                        c.telegram.bot.remove_message_handler(handle_new_user_id)
                        return
                    if m.text.lower() == "отмена":
                        update_settings_panel(c, chat_id, message_id)
                        c.telegram.bot.remove_message_handler(handle_new_user_id)
                        return
                    try:
                        new_user_id = int(m.text.strip())
                    except ValueError:
                        c.telegram.bot.send_message(chat_id, "❌ User ID должен быть числом!")
                        return
                    config["user_id"] = new_user_id
                    USER_ID = new_user_id
                    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
                        json.dump(config, f, indent=4, ensure_ascii=False)
                    c.telegram.bot.send_message(chat_id, "✅ User ID обновлен!")
                    update_settings_panel(c, chat_id, message_id)
                    c.telegram.bot.remove_message_handler(handle_new_user_id)

                c.telegram.bot.register_next_step_handler(call.message, handle_new_user_id)

            elif data == "show_wallet_address":
                try:
                    from tonutils.client import TonapiClient
                    from tonutils.wallet import WalletV5R1
                    client = TonapiClient(api_key=API_KEY, is_testnet=IS_TESTNET)
                    wallet, _, _, _ = WalletV5R1.from_mnemonic(client, MNEMONIC)
                    wallet_address = wallet.address.to_str(is_bounceable=False)
                    c.telegram.bot.send_message(
                        chat_id,
                        sanitize_telegram_text(
                            f"💳 Адрес вашего TON-кошелька:\n\n<code>{wallet_address}</code>\n\n"
                            "Отправьте TON на этот адрес для пополнения баланса."
                        ),
                        parse_mode="HTML"
                    )
                except Exception as _addr_err:
                    c.telegram.bot.send_message(
                        chat_id,
                        sanitize_telegram_text(f"❌ Ошибка получения адреса: {_addr_err}")
                    )

            elif data == "back_to_main":
                update_config_panel(c, chat_id, message_id)

            elif data == "cancel":
                update_settings_panel(c, chat_id, message_id)

            elif data == "toggle_balance_format":
                config["USE_OLD_BALANCE"] = not config["USE_OLD_BALANCE"]
                balance_type = "старый формат (без деления на 10^9)" if config[
                    "USE_OLD_BALANCE"] else "новый формат (с делением на 10^9)"
                with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
                    json.dump(config, f, indent=4, ensure_ascii=False)
                c.telegram.bot.send_message(
                    chat_id,
                    sanitize_telegram_text(f"✅ Формат баланса изменен на {balance_type}")
                )
                update_settings_panel(c, chat_id, message_id)

        except Exception as e:
            c.telegram.bot.send_message(
                chat_id,
                sanitize_telegram_text(f"❌ Ошибка: {str(e)}")
            )

    @c.telegram.bot.callback_query_handler(func=lambda call: call.data.startswith("refund_order_"))
    def refund_order_callback(call):
        order_id = call.data.replace("refund_order_", "")
        callback_chat_id = call.message.chat.id
        try:
            c.account.refund(order_id)
            msg = f"✅ Заказ #{order_id} возвращён."
        except Exception as e:
            msg = f"❌ Ошибка при возврате заказа #{order_id}: {e}"
        c.telegram.bot.answer_callback_query(call.id, text=msg, show_alert=True)
        c.telegram.bot.send_message(callback_chat_id, sanitize_telegram_text(msg))


BIND_TO_PRE_INIT = [init_commands]
BIND_TO_NEW_MESSAGE = [stars_auto]
BIND_TO_NEW_ORDER = [handle_new_order_stars]
BIND_TO_DELETE = []


def shutdown():
    if payment_processor is not None:
        try:
            payment_processor.loop.call_soon_threadsafe(payment_processor.loop.stop)
            payment_processor.thread.join(timeout=5)
        except Exception as e:
            logger.error(f"Ошибка при завершении PaymentProcessor: {e}")


atexit.register(shutdown)
