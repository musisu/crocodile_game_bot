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
SPECIAL_HASHTAG_CHAT = -5214033440
TOP_REWARD = {1: 20, 2: 10, 3: 5}

# ---------- WORDS ----------
with open("words.txt", "r", encoding="utf-8") as f:
    WORDS = [w.strip().lower() for w in f.readlines()]
shuffle(WORDS)

# ---------- GLOBAL MESSAGE HANDLER ----------
def global_text_handler(update, context):
    if not update.message or not update.message.text:
        return

    text = update.message.text.lower()
    user = update.message.from_user
    username = user.username or user.first_name

    # 📝 Рахуємо повідомлення ЗАВЖДИ
    chat_stats = context.chat_data.setdefault("chat_messages", {})
    chat_stats[username] = chat_stats.get(username, 0) + 1

    # 👹 Реакція на "гетеро"
    if "гетеро" in text:
        update.message.reply_text("👹")
        coins = context.bot_data.setdefault("coins", {})
        coins[username] = max(coins.get(username, 0) - 1, 0)

    # #️⃣ Хештег +50 монет
    if (
        "#" in text
        and update.message.chat.id == SPECIAL_HASHTAG_CHAT
    ):
        coins = context.bot_data.setdefault("coins", {})
        coins[username] = coins.get(username, 0) + 50

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
    username = user.username or user.first_name

    if (
        context.chat_data.get("is_playing")
        and user.id != context.chat_data.get("current_player")
        and text == context.chat_data.get("current_word")
    ):
        update.message.reply_text(f"{user.first_name} вгадав слово!")

        coins = context.bot_data.setdefault("coins", {})
        rating = context.chat_data.setdefault("rating", {})
        rating[username] = rating.get(username, 0) + 1

        position = sorted(rating.values(), reverse=True).index(rating[username]) + 1
        coins[username] = coins.get(username, 0) + TOP_REWARD.get(position, 0)

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
    coins = context.bot_data.get("coins", {}).get(username, 0)
    update.message.reply_text(f"@{username}, у вас {coins} монет")

# ---------- TOPS ----------
def top_money(update, context):
    coins = context.bot_data.get("coins", {})
    if not coins:
        update.message.reply_text("Поки що ніхто не має монет.")
        return

    top = sorted(coins.items(), key=lambda x: x[1], reverse=True)[:5]
    msg = "\n".join(f"{i+1}. @{u}: {c}" for i, (u, c) in enumerate(top))
    update.message.reply_text(f"💰 Топ за монетами:\n{msg}")

def top_messages(update, context):
    stats = context.chat_data.get("chat_messages", {})
    if not stats:
        update.message.reply_text("Поки що немає статистики.")
        return

    top = sorted(stats.items(), key=lambda x: x[1], reverse=True)[:5]
    msg = "\n".join(f"{i+1}. {u}: {c}" for i, (u, c) in enumerate(top))
    update.message.reply_text(f"📝 Топ повідомлень:\n{msg}")

# ---------- MAIN ----------
def main():
    token = os.environ["TOKEN"]
    updater = Updater(token, use_context=True)
    dp = updater.dispatcher

    # 🌍 ГЛОБАЛЬНІ РЕЧІ — ПЕРШІ
    dp.add_handler(
        MessageHandler(Filters.text & ~Filters.command, global_text_handler),
        group=0
    )

    # 🎮 ГРА
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
    dp.add_handler(conv, group=1)

    # 📊 Команди
    dp.add_handler(CommandHandler("wallet", wallet))
    dp.add_handler(CommandHandler("top_money", top_money))
    dp.add_handler(CommandHandler("top", top_messages))

    updater.start_polling()
    updater.idle()

if __name__ == "__main__":
    main()
