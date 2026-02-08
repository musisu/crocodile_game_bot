#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
from random import shuffle, choice
from datetime import datetime
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Updater, CommandHandler, MessageHandler, Filters,
    ConversationHandler, CallbackQueryHandler
)
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

GUESSING, CHOOSING_PLAYER = range(2)
SPECIAL_HASHTAG_CHAT = -5214033440  # конкретний чат для #
TOP_REWARD = {1: 20, 2: 10, 3: 5}

# ---------- WORDS ----------
WORDS = []
with open("words.txt", "r", encoding="utf-8") as f:
    WORDS = [w.strip().lower() for w in f.readlines()]
shuffle(WORDS)

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

    # Реакція на "гетеро" та "мальви"
    if "гетеро" in text:
        update.message.reply_text("🍽️")
    if "мальви" in text:
        update.message.reply_text("👀")

    # Логіка крокодила
    if (
        context.chat_data.get("is_playing")
        and user.id != context.chat_data.get("current_player")
        and text == context.chat_data.get("current_word")
    ):
        update.message.reply_text(f"{user.first_name} вгадав слово!")

        username = user.username or user.first_name
        # Рейтинг у чаті
        rating = context.chat_data.setdefault('rating', {})
        rating[username] = rating.get(username, 0) + 1
        context.chat_data['rating'] = rating

        # Монети
        coins = context.bot_data.setdefault('coins', {})
        # визначення позиції
        position = sorted(rating.values(), reverse=True).index(rating[username]) + 1
        coins[username] = coins.get(username, 0) + TOP_REWARD.get(position, 0)
        context.bot_data['coins'] = coins

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


# ---------- COINS ----------
def wallet(update, context):
    user = update.message.from_user
    username = user.username or user.first_name
    coins = context.bot_data.get('coins', {}).get(username, 0)
    update.message.reply_text(f"@{username}, у вас {coins} монет")


def add_coins(update, context):
    try:
        args = context.args
        if len(args) != 2:
            update.message.reply_text("Використання: /add username amount")
            return
        username = args[0].lstrip("@")
        amount = int(args[1])
        coins = context.bot_data.setdefault('coins', {})
        coins[username] = coins.get(username, 0) + amount
        update.message.reply_text(f"Додано {amount} монет @{username}")
    except Exception as e:
        update.message.reply_text(f"Помилка: {e}")


def deduct_coins(update, context):
    try:
        args = context.args
        if len(args) != 2:
            update.message.reply_text("Використання: /deduct username amount")
            return
        username = args[0].lstrip("@")
        amount = int(args[1])
        coins = context.bot_data.setdefault('coins', {})
        coins[username] = max(coins.get(username, 0) - amount, 0)
        update.message.reply_text(f"Віднято {amount} монет у @{username}")
    except Exception as e:
        update.message.reply_text(f"Помилка: {e}")


# ---------- HASHTAG COINS ----------
def hashtag_coins(update, context):
    if update.message.chat.id != SPECIAL_HASHTAG_CHAT:
        return
    text = update.message.text
    if "#" in text:
        username = update.message.from_user.username or update.message.from_user.first_name
        coins = context.bot_data.setdefault('coins', {})
        coins[username] = coins.get(username, 0) + 50
        context.bot_data['coins'] = coins


# ---------- TOP ----------
def top_money(update, context):
    coins = context.bot_data.get('coins', {})
    if not coins:
        update.message.reply_text("Поки що ніхто не має монет.")
        return
    top_list = sorted(coins.items(), key=lambda x: x[1], reverse=True)[:5]
    msg = "\n".join([f"{i+1}. @{user}: {amount} монет" for i, (user, amount) in enumerate(top_list)])
    update.message.reply_text(f"💰 Топ 5 за монетами:\n{msg}")


def top_messages(update, context):
    chat_rating = context.chat_data.get('rating', {})
    if not chat_rating:
        update.message.reply_text("Поки що немає активності у чаті.")
        return
    top_list = sorted(chat_rating.items(), key=lambda x: x[1], reverse=True)[:5]
    msg = "\n".join([f"{i+1}. {user}: {count} повідомлень" for i, (user, count) in enumerate(top_list)])
    update.message.reply_text(f"📊 Топ 5 за повідомленнями:\n{msg}")


# ---------- MAIN ----------
def main():
    token = os.environ["TOKEN"]
    updater = Updater(token, use_context=True)
    dp = updater.dispatcher

    # Гра
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

    # Монети
    dp.add_handler(CommandHandler("wallet", wallet))
    dp.add_handler(CommandHandler("add", add_coins))
    dp.add_handler(CommandHandler("deduct", deduct_coins))
    dp.add_handler(MessageHandler(Filters.text & ~Filters.command, hashtag_coins))

    # Топи
    dp.add_handler(CommandHandler("top_money", top_money))
    dp.add_handler(CommandHandler("top", top_messages))

    # Реакції
    dp.add_handler(MessageHandler(Filters.text & ~Filters.command, guesser))  # для крокодила
    dp.add_handler(MessageHandler(Filters.text & ~Filters.command, plate_on_hetero))  # "гетеро" / "мальви"

    updater.start_polling()
    updater.idle()


if __name__ == "__main__":
    main()
