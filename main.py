#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import json
import random
from random import shuffle, choice
from datetime import datetime
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Updater, CommandHandler, MessageHandler, Filters,
    ConversationHandler, CallbackQueryHandler
)
import logging

# ================== LOGGING ==================
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ================== CONSTANTS ==================
GUESSING, CHOOSING_PLAYER = range(2)
SPECIAL_HASHTAG_CHAT = -5214033440
TOP_REWARD = {1: 20, 2: 10, 3: 5}
COINS_FILE = "coins.json"

# ================== COINS STORAGE ==================
COINS = {}

def load_coins():
    global COINS
    try:
        with open(COINS_FILE, "r", encoding="utf-8") as f:
            COINS = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        COINS = {}

def save_coins():
    with open(COINS_FILE, "w", encoding="utf-8") as f:
        json.dump(COINS, f, ensure_ascii=False, indent=2)

# ================== ADMIN CHECK ==================
def is_admin(update, context):
    try:
        member = context.bot.get_chat_member(
            update.effective_chat.id,
            update.effective_user.id
        )
        return member.status in ("administrator", "creator")
    except Exception:
        return False

# ================== WORDS ==================
with open("words.txt", "r", encoding="utf-8") as f:
    WORDS = [w.strip().lower() for w in f.readlines()]
shuffle(WORDS)

# ================== GLOBAL TEXT HANDLER ==================
def global_text_handler(update, context):
    if not update.message or not update.message.text:
        return

    text = update.message.text.lower()
    user = update.message.from_user
    username = user.username or user.first_name

    # 📝 message counter
    stats = context.chat_data.setdefault("chat_messages", {})
    stats[username] = stats.get(username, 0) + 1

    # 👹 "гетеро"
    if "гетеро" in text:
        COINS[username] = max(COINS.get(username, 0) - 1, 0)
        save_coins()
        update.message.reply_text("👹")
        update.message.reply_text(f"@{username}, -1 монета")

    # #️⃣ hashtag reward
    if "#" in text and update.message.chat.id == SPECIAL_HASHTAG_CHAT:
        COINS[username] = COINS.get(username, 0) + 50
        save_coins()
        update.message.reply_text(f"🎉 @{username}, +50 монет")

# ================== GAME ==================
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

        rating = context.chat_data.setdefault("rating", {})
        rating[username] = rating.get(username, 0) + 1

        pos = sorted(rating.values(), reverse=True).index(rating[username]) + 1
        COINS[username] = COINS.get(username, 0) + TOP_REWARD.get(pos, 0)
        save_coins()

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
    q = update.callback_query
    if q.from_user.id == context.chat_data.get("current_player"):
        q.answer(context.chat_data["current_word"], show_alert=True)
    else:
        q.answer("Не можна 👀", show_alert=True)
    return GUESSING

def next_word(update, context):
    q = update.callback_query
    if q.from_user.id == context.chat_data.get("current_player"):
        context.chat_data["current_word"] = choice(WORDS)
        q.answer(context.chat_data["current_word"], show_alert=True)
    else:
        q.answer("Не можна", show_alert=True)
    return GUESSING

# ================== COMMANDS ==================
def wallet(update, context):
    username = update.message.from_user.username or update.message.from_user.first_name
    update.message.reply_text(f"@{username}, у вас {COINS.get(username, 0)} монет")

def add_coins(update, context):
    if not is_admin(update, context):
        return update.message.reply_text("⛔ Тільки адмін")

    if not update.message.reply_to_message or len(context.args) != 1:
        return update.message.reply_text("❗ /add 10 (reply)")

    amount = int(context.args[0])
    user = update.message.reply_to_message.from_user
    username = user.username or user.first_name

    COINS[username] = COINS.get(username, 0) + amount
    save_coins()
    update.message.reply_text(f"✅ @{username} +{amount}")

def deduct_coins(update, context):
    if not is_admin(update, context):
        return update.message.reply_text("⛔ Тільки адмін")

    if not update.message.reply_to_message or len(context.args) != 1:
        return update.message.reply_text("❗ /deduct 5 (reply)")

    amount = int(context.args[0])
    user = update.message.reply_to_message.from_user
    username = user.username or user.first_name

    COINS[username] = max(COINS.get(username, 0) - amount, 0)
    save_coins()
    update.message.reply_text(f"✅ @{username} -{amount}")

def gift_coins(update, context):
    if not update.message.reply_to_message or len(context.args) != 1:
        return update.message.reply_text("❗ Використання: /gift 10 (reply)")

    try:
        amount = int(context.args[0])
        if amount <= 0:
            raise ValueError
    except ValueError:
        return update.message.reply_text("❗ Кількість має бути додатнім числом")

    from_user = update.message.from_user
    to_user = update.message.reply_to_message.from_user

    from_name = from_user.username or from_user.first_name
    to_name = to_user.username or to_user.first_name

    if COINS.get(from_name, 0) < amount:
        return update.message.reply_text("💸 Недостатньо монет")

    COINS[from_name] -= amount
    COINS[to_name] = COINS.get(to_name, 0) + amount
    save_coins()

    update.message.reply_text(
        f"🎁 @{from_name} подарував @{to_name} {amount} монет"
    )

def steal_coins(update, context):
    if not update.message.reply_to_message:
        return update.message.reply_text("❗ Використовуй /steal відповіддю")

    thief = update.message.from_user
    victim = update.message.reply_to_message.from_user

    thief_name = thief.username or thief.first_name
    victim_name = victim.username or victim.first_name

    if thief.id == victim.id:
        return update.message.reply_text("🤨 Сам у себе красти не можна")

    # поточний шанс
    chance = STEAL_CHANCE.get(thief_name, STEAL_BASE_CHANCE)

    # перевірка
    if random.random() < chance:
        fine = 50
        COINS[thief_name] = max(COINS.get(thief_name, 0) - fine, 0)

        # 🔥 скид шансів
        STEAL_CHANCE[thief_name] = STEAL_BASE_CHANCE
        save_coins()

        return update.message.reply_text(
            f"🚓 @{thief_name} попався!\n"
            f"💸 Штраф {fine} монет\n"
            f"🔄 Шанс скинуто до 40%"
        )

    # успішна крадіжка
    steal_amount = random.randint(0, 20)
    victim_balance = COINS.get(victim_name, 0)
    real_amount = min(steal_amount, victim_balance)

    COINS[victim_name] = victim_balance - real_amount
    COINS[thief_name] = COINS.get(thief_name, 0) + real_amount

    # 📈 підвищуємо шанс
    new_chance = min(chance + STEAL_STEP, STEAL_MAX_CHANCE)
    STEAL_CHANCE[thief_name] = new_chance

    save_coins()

    update.message.reply_text(
        f"🕵️ @{thief_name} поцупив {real_amount} монет у @{victim_name}!\n"
        f"⚠️ Новий шанс попастися: {int(new_chance * 100)}%"
    )

def top_money(update, context):
    if not COINS:
        return update.message.reply_text("Поки що немає монет")

    top = sorted(COINS.items(), key=lambda x: x[1], reverse=True)[:5]
    msg = "\n".join(f"{i+1}. @{u}: {c}" for i, (u, c) in enumerate(top))
    update.message.reply_text(f"💰 Топ монет:\n{msg}")

def top_messages(update, context):
    stats = context.chat_data.get("chat_messages", {})
    if not stats:
        return update.message.reply_text("Немає статистики")

    top = sorted(stats.items(), key=lambda x: x[1], reverse=True)[:5]
    msg = "\n".join(f"{i+1}. {u}: {c}" for i, (u, c) in enumerate(top))
    update.message.reply_text(f"📝 Топ повідомлень:\n{msg}")

# ================== MAIN ==================
def main():
    load_coins()  # 🔥 КРИТИЧНО

    updater = Updater(os.environ["TOKEN"], use_context=True)
    dp = updater.dispatcher

    dp.add_handler(MessageHandler(Filters.text & ~Filters.command, global_text_handler), group=0)

    conv = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            GUESSING: [
                MessageHandler(Filters.text & ~Filters.command, guesser),
                CallbackQueryHandler(see_word, pattern="^look$"),
                CallbackQueryHandler(next_word, pattern="^next$")
            ],
            CHOOSING_PLAYER: [CallbackQueryHandler(next_player)],
        },
        fallbacks=[CommandHandler("stop", stop)],
        per_user=False
    )
    dp.add_handler(conv, group=1)

    dp.add_handler(CommandHandler("wallet", wallet))
    dp.add_handler(CommandHandler("top_money", top_money))
    dp.add_handler(CommandHandler("top", top_messages))
    dp.add_handler(CommandHandler("add", add_coins))
    dp.add_handler(CommandHandler("deduct", deduct_coins))
    dp.add_handler(CommandHandler("gift", gift_coins))
    dp.add_handler(CommandHandler("steal", steal_coins))

    updater.start_polling()
    updater.idle()

if __name__ == "__main__":
    main()
