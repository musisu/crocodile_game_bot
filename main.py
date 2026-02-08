#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
from random import shuffle, choice
from datetime import datetime, date
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Updater, CommandHandler, MessageHandler, Filters,
    ConversationHandler, CallbackQueryHandler
)
import logging
from apscheduler.schedulers.background import BackgroundScheduler
import pytz

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

GUESSING, CHOOSING_PLAYER = range(2)

# ---------- WORDS ----------
WORDS = []
with open("words.txt", "r", encoding="utf-8") as f:
    WORDS = [w.strip().lower() for w in f.readlines()]
shuffle(WORDS)

# ---------- GLOBAL DATA ----------
wallets = {}          # {user_id: coins}
daily_messages = {}   # {chat_id: {user_id: count}}
SPECIAL_CHAT_ID = -1001234567890  # встав свій id чату
SPECIAL_HASH_COINS = 50

# ---------- UTILS ----------
def add_coins(user_id, amount):
    wallets[user_id] = wallets.get(user_id, 0) + amount

def sub_coins(user_id, amount):
    wallets[user_id] = max(wallets.get(user_id, 0) - amount, 0)

def get_wallet(user_id):
    return wallets.get(user_id, 0)

# ---------- GAME ----------
def start(update, context):
    if context.chat_data.get("is_playing"):
        update.message.reply_text("Гра вже почалась")
        return GUESSING

    user = update.message.from_user
    context.chat_data["is_playing"] = True
    context.chat_data["current_player"] = user.id
    context.chat_data["current_word"] = choice(WORDS)

    keyboard = [[
        InlineKeyboardButton("Подивитись слово", callback_data="look"),
        InlineKeyboardButton("Наступне слово", callback_data="next")
    ]]

    update.message.reply_text(
        f"[{user.first_name}](tg://user?id={user.id}) пояснює слово!",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )
    return GUESSING

def stop(update, context):
    context.chat_data.clear()
    update.message.reply_text("Гру зупинено")
    return ConversationHandler.END

def guesser(update, context):
    text = update.message.text.lower()
    user = update.message.from_user

    # 🔥 Реакція на ключові слова
    if "гетеро" in text:
        sub_coins(user.id, 1)
        update.message.reply_text("🍽️ -1 монета за гетеро")
        return GUESSING
    if "мальви" in text:
        update.message.reply_text("👀")
        return GUESSING
    if "кішпари" in text:
        update.message.reply_text("🍽️")
        return GUESSING

    # Основна логіка гри
    if (
        context.chat_data.get("is_playing")
        and user.id != context.chat_data.get("current_player")
        and text == context.chat_data.get("current_word")
    ):
        add_coins(user.id, 5)
        update.message.reply_text(f"{user.first_name} вгадав слово! +5 монет")
        context.chat_data["winner"] = user.id
        context.chat_data["win_time"] = datetime.now()
        return CHOOSING_PLAYER

    return GUESSING

def next_player(update, context):
    query = update.callback_query
    query.answer()
    user = query.from_user
    context.chat_data["current_player"] = user.id
    context.chat_data["current_word"] = choice(WORDS)

    keyboard = [[
        InlineKeyboardButton("Подивитись слово", callback_data="look"),
        InlineKeyboardButton("Наступне слово", callback_data="next")
    ]]
    query.edit_message_text(
        f"[{user.first_name}](tg://user?id={user.id}) пояснює слово!",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )
    return GUESSING

def see_word(update, context):
    query = update.callback_query
    if query.from_user.id == context.chat_data.get("current_player"):
        query.answer(context.chat_data.get("current_word"), show_alert=True)
    else:
        query.answer("Не можна 👀", show_alert=True)
    return GUESSING

def next_word(update, context):
    query = update.callback_query
    if query.from_user.id == context.chat_data.get("current_player"):
        context.chat_data["current_word"] = choice(WORDS)
        query.answer(context.chat_data["current_word"], show_alert=True)
    else:
        query.answer("Не можна", show_alert=True)
    return GUESSING

# ---------- WALLET ----------
def wallet(update, context):
    user = update.message.from_user
    coins = get_wallet(user.id)
    update.message.reply_text(f"💰 У тебе {coins} монет")

# ---------- DAILY MESSAGES ----------
def track_daily_messages(update, context):
    chat_id = update.effective_chat.id
    user_id = update.message.from_user.id
    today = date.today()

    if chat_id not in daily_messages:
        daily_messages[chat_id] = {}
    if user_id not in daily_messages[chat_id]:
        daily_messages[chat_id][user_id] = 0

    daily_messages[chat_id][user_id] += 1

# ---------- SPECIAL CHAT TAGS ----------
def check_special_chat_message(update, context):
    chat_id = update.effective_chat.id
    user_id = update.message.from_user.id
    text = update.message.text
    if chat_id == SPECIAL_CHAT_ID and "#" in text:
        add_coins(user_id, SPECIAL_HASH_COINS)
        update.message.reply_text(f"🎉 +{SPECIAL_HASH_COINS} монет за повідомлення з #!")

# ---------- DAILY TOP ----------
def send_daily_top(context):
    bot = context.bot
    for chat_id, users in daily_messages.items():
        sorted_users = sorted(users.items(), key=lambda x: x[1], reverse=True)
        top_text = "🏆 Топ за сьогодні:\n"
        for i, (user_id, count) in enumerate(sorted_users[:3]):
            coins_reward = [20, 10, 5][i]
            add_coins(user_id, coins_reward)
            top_text += f"{i+1}. [User](tg://user?id={user_id}): {count} повідомлень (+{coins_reward} монет)\n"
        bot.send_message(chat_id=chat_id, text=top_text, parse_mode="Markdown")

    daily_messages.clear()

# ---------- MAIN ----------
def main():
    token = os.environ["TOKEN"]
    updater = Updater(token, use_context=True)
    dp = updater.dispatcher

    # Основні хендлери
    dp.add_handler(CommandHandler("wallet", wallet))
    dp.add_handler(MessageHandler(Filters.text & ~Filters.command, track_daily_messages))
    dp.add_handler(MessageHandler(Filters.text & ~Filters.command, check_special_chat_message))

    conv = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            GUESSING: [
                MessageHandler(Filters.text & ~Filters.command, guesser),
                CallbackQueryHandler(see_word, pattern="^look$"),
                CallbackQueryHandler(next_word, pattern="^next$")
            ],
            CHOOSING_PLAYER: [
                CallbackQueryHandler(next_player)
            ],
        },
        fallbacks=[CommandHandler("stop", stop)],
        per_user=False
    )
    dp.add_handler(conv)

    # Scheduler для щоденного топу за київським часом
    scheduler = BackgroundScheduler(timezone=pytz.timezone("Europe/Kiev"))
    scheduler.add_job(lambda: send_daily_top(updater), "cron", hour=0, minute=0)
    scheduler.start()

    updater.start_polling()
    updater.idle()

if __name__ == "__main__":
    main()
