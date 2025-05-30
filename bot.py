# bot.py

import os
import logging
import threading
from datetime import datetime

import pytz, tzlocal, apscheduler.util
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from flask import Flask, jsonify  # лёгкий HTTP-сервер

from telegram import ReplyKeyboardMarkup, ReplyKeyboardRemove, Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ConversationHandler,
    ContextTypes,
    filters,
)

# ─── «Монкей-патч» для tzlocal/APSscheduler ────────────────────────────────
_LOCAL_TZ = pytz.timezone("Europe/Vienna")
apscheduler.util.astimezone    = lambda obj=None, tz=None: _LOCAL_TZ
apscheduler.util.get_localzone = lambda: _LOCAL_TZ
tzlocal.get_localzone          = lambda: _LOCAL_TZ
# ────────────────────────────────────────────────────────────────────────────

# ───────────── Логирование ─────────────────────────────────────────────────
logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)
# ────────────────────────────────────────────────────────────────────────────

# ───────────── Google Sheets ───────────────────────────────────────────────
CREDENTIALS_FILE = "credentials.json"
SHEET_NAME       = "Финансы"

def connect_to_sheet():
    scope = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ]
    creds  = ServiceAccountCredentials.from_json_keyfile_name(CREDENTIALS_FILE, scope)
    client = gspread.authorize(creds)
    return client.open(SHEET_NAME).sheet1

def add_transaction(sheet, date, bank, category, amount, comment=""):
    row = [date, bank, category, amount, comment]
    sheet.append_row(row)
# ────────────────────────────────────────────────────────────────────────────

# ───────────── Conversation States ─────────────────────────────────────────
DATE, BANK, CATEGORY, AMOUNT, COMMENT = range(5)
# ────────────────────────────────────────────────────────────────────────────

BANKS = [
    "Озон", "Альфа", "Яндекс", "Озон рассрочка", "Наличные",
    "Тинькофф Соня", "Тинькофф кредитка Соня", "Озон Соня",
    "Сбер Соня", "Сбер Кредит Соня", "USDT", "USD"
]
CATEGORIES = [
    "Еда", "Развлечения", "Кафе, рестораны", "Интернет", "Мобильная связь",
    "... полный список ...", "Перевод"
]

def chunk(lst, n):
    for i in range(0, len(lst), n):
        yield lst[i:i+n]
# ────────────────────────────────────────────────────────────────────────────

# ───────────── Handlers ────────────────────────────────────────────────────

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("Привет! Я готов записывать твои личные финансы.")
    await update.message.reply_text(
        "Введите дату операции:",
        reply_markup=ReplyKeyboardMarkup([["Сегодня"]], one_time_keyboard=True, resize_keyboard=True)
    )
    return DATE

async def handle_date(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text.strip()
    if text == "Сегодня":
        dt = datetime.now(_LOCAL_TZ)
    else:
        try:
            day, month = map(int, text.split("."))
            dt = datetime(datetime.now().year, month, day)
        except:
            return await update.message.reply_text(
                "Неверный формат. Введи «Сегодня» или ДД.MM (например, 21.05):"
            )
    context.user_data["date"] = dt.strftime("%Y-%m-%d")
    await update.message.reply_text(
        f"Дата: {context.user_data['date']}\nВыбери банк:",
        reply_markup=ReplyKeyboardMarkup([[b] for b in BANKS], one_time_keyboard=True, resize_keyboard=True)
    )
    return BANK

async def handle_bank(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    choice = update.message.text
    if choice not in BANKS:
        return await update.message.reply_text("Пожалуйста, выбери банк кнопкой.")
    context.user_data["bank"] = choice
    kb = list(chunk(CATEGORIES, 4))
    await update.message.reply_text(
        f"Банк: {choice}\nКакая категория?",
        reply_markup=ReplyKeyboardMarkup(kb, one_time_keyboard=True, resize_keyboard=True)
    )
    return CATEGORY

async def handle_category(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    cat = update.message.text
    if cat not in CATEGORIES:
        return await update.message.reply_text("Пожалуйста, выбери категорию кнопкой.")
    context.user_data["category"] = cat
    await update.message.reply_text(
        f"Категория: {cat}\nТеперь введи сумму (только число):",
        reply_markup=ReplyKeyboardRemove()
    )
    return AMOUNT

async def handle_amount(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text.strip()
    try:
        amt = float(text)
    except:
        return await update.message.reply_text("Нужно ввести число. Попробуй ещё раз:")
    context.user_data["amount"] = amt
    await update.message.reply_text(
        "Есть комментарий?",
        reply_markup=ReplyKeyboardMarkup([["Нет"]], one_time_keyboard=True, resize_keyboard=True)
    )
    return COMMENT

async def handle_comment(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text.strip()
    comment = "" if text == "Нет" else text
    context.user_data["comment"] = comment

    sheet = connect_to_sheet()
    add_transaction(
        sheet,
        context.user_data["date"],
        context.user_data["bank"],
        context.user_data["category"],
        context.user_data["amount"],
        context.user_data["comment"]
    )

    data = context.user_data
    await update.message.reply_text(
        "✅ Записано:\n"
        f"Дата: {data['date']}\n"
        f"Банк: {data['bank']}\n"
        f"Категория: {data['category']}\n"
        f"Сумма: {data['amount']}\n"
        f"Комментарий: {comment or '—'}\n\n"
        "Присылай следующую операцию — введите дату:",
        reply_markup=ReplyKeyboardMarkup([["Сегодня"]], one_time_keyboard=True, resize_keyboard=True)
    )
    return DATE

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text(
        "Отменено. Начни заново командой /start",
        reply_markup=ReplyKeyboardRemove()
    )
    return ConversationHandler.END

# ───────────── Telegram Bot Setup ──────────────────────────────────────────

def run_bot():
    TOKEN = os.environ["TELEGRAM_TOKEN"]
    app = ApplicationBuilder().token(TOKEN).build()

    conv = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            DATE:     [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_date)],
            BANK:     [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_bank)],
            CATEGORY: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_category)],
            AMOUNT:   [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_amount)],
            COMMENT:  [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_comment)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        allow_reentry=True,
    )
    app.add_handler(conv)

    # Запускаем polling (фоновый цикл получения обновлений)
    app.run_polling()

# ───────────── HTTP Health-check Server ────────────────────────────────────

http_app = Flask(__name__)

@http_app.route("/", methods=["GET"])
def health_check():
    return jsonify({"status": "ok"})

# ───────────── Entry Point ─────────────────────────────────────────────────

if __name__ == "__main__":
    # 1) Стартуем бот в отдельном потоке
    threading.Thread(target=run_bot, daemon=True).start()

    # 2) Запускаем HTTP-сервер для Cloud Run health-checks
    port = int(os.environ.get("PORT", "8080"))
    http_app.run(host="0.0.0.0", port=port)
