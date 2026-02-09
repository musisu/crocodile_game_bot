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
STEAL_BASE_CHANCE = 0.4
STEAL_STEP = 0.2
STEAL_MAX_CHANCE = 0.9

STEAL_CHANCE = {}
# ================== COINS STORAGE ==================
DATA_FILE = "coins.json"  # залишаємо старий файл
COINS = {}                 # залишаємо баланс гравців
MARRIAGES = {}             # нове для шлюбів
INVENTORY = {}  
# структура:
# INVENTORY = {
#   "username": {
#       "rings": ["silver", "gold"]
#   }
# }

RINGS = {        # каблучки і їх ціни
    "silver": 200,
    "gold": 500,
    "diamond": 1000
}

def load_data():
    global COINS, MARRIAGES, INVENTORY
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            COINS = data.get("coins", {})
            MARRIAGES = data.get("marriages", {})
            INVENTORY = data.get("inventory", {})
    except (FileNotFoundError, json.JSONDecodeError):
        COINS = {}
        MARRIAGES = {}
        INVENTORY = {}

def save_data():
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump({
            "coins": COINS,
            "marriages": MARRIAGES,
            "inventory": INVENTORY
        }, f, ensure_ascii=False, indent=2)

def is_married(username):
    return username in MARRIAGES


def get_shared_owner(username):
    if not is_married(username):
        return None
    return username  # будь-хто з пари — ключ


def get_balance(username):
    if is_married(username):
        return MARRIAGES[username]["shared"]
    return COINS.get(username, 0)


def spend_coins(username, amount):
    if is_married(username):
        if MARRIAGES[username]["shared"] < amount:
            return False
        MARRIAGES[username]["shared"] -= amount
        return True
    else:
        if COINS.get(username, 0) < amount:
            return False
        COINS[username] -= amount
        return True


def add_coins_to_user(username, amount):
    if is_married(username):
        MARRIAGES[username]["shared"] += amount
    else:
        COINS[username] = COINS.get(username, 0) + amount

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
        save_data()
        update.message.reply_text("👹")
        update.message.reply_text(f"@{username}, -1 монета")

    # #️⃣ hashtag reward
    if "#" in text and update.message.chat.id == SPECIAL_HASHTAG_CHAT:
        COINS[username] = COINS.get(username, 0) + 50
        save_data()
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
        save_data()

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

    # Якщо гравець у шлюбі
    if username in MARRIAGES:
        shared_balance = MARRIAGES[username]["shared"]
        partner_name = MARRIAGES[username]["partner"]
        update.message.reply_text(
            f"💑 @{username} у шлюбі з @{partner_name}\n"
            f"💰 Спільний баланс: {shared_balance} монет"
        )
    else:
        # Інакше показуємо особистий баланс
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
    save_data()
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
    save_data()

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
    chance = STEAL_CHANCE.get(thief_name)
    if chance is None:
        chance = STEAL_BASE_CHANCE

    # перевірка
    if random.random() < chance:
        fine = 50
        COINS[thief_name] = max(COINS.get(thief_name, 0) - fine, 0)

        # 🔥 скид шансів
        STEAL_CHANCE[thief_name] = STEAL_BASE_CHANCE
        save_data()

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

    save_data()

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

# ================== MARRIAGE & RINGS COMMANDS ==================

def buy_ring(update, context):
    if len(context.args) != 1:
        return update.message.reply_text(
            f"❗ /buy_ring <тип> | Доступні: {', '.join(RINGS.keys())}"
        )

    ring = context.args[0].lower()
    if ring not in RINGS:
        return update.message.reply_text("❗ Невірний тип каблучки")

    username = update.message.from_user.username or update.message.from_user.first_name
    price = RINGS[ring]

    if not spend_coins(username, price):
        return update.message.reply_text("💸 Недостатньо коштів")

    INVENTORY.setdefault(username, {"rings": []})
    INVENTORY[username]["rings"].append(ring)

    save_data()
    update.message.reply_text(f"💍 @{username} купив каблучку {ring}")
def marry(update, context):
    if not update.message.reply_to_message:
        return update.message.reply_text("❗ /marry у відповідь на партнера")

    user = update.message.from_user
    partner = update.message.reply_to_message.from_user

    u = user.username or user.first_name
    p = partner.username or partner.first_name

    if u in MARRIAGES or p in MARRIAGES:
        return update.message.reply_text("💔 Хтось уже в шлюбі")

    rings = INVENTORY.get(u, {}).get("rings", [])
    if not rings:
        return update.message.reply_text("💍 У тебе немає каблучки")

    if not spend_coins(u, 500):
        return update.message.reply_text("💸 Потрібно 500 монет")

    ring = rings.pop(0)  # перша каблучка
    INVENTORY.setdefault(p, {"rings": []})
    INVENTORY[p]["rings"].append(ring)

    shared = get_balance(u) + get_balance(p)

    COINS[u] = 0
    COINS[p] = 0

    MARRIAGES[u] = {"partner": p, "shared": shared}
    MARRIAGES[p] = {"partner": u, "shared": shared}

    save_data()
    update.message.reply_text(
        f"💒 @{u} і @{p} одружились!\n"
        f"💍 Каблучка тепер у @{p}\n"
        f"💰 Спільний баланс: {shared}"
    )

def divorce(update, context):
    u = update.message.from_user.username or update.message.from_user.first_name

    if u not in MARRIAGES:
        return update.message.reply_text("❗ Ти не в шлюбі")

    p = MARRIAGES[u]["partner"]
    shared = MARRIAGES[u]["shared"]

    if shared < 500:
        return update.message.reply_text("💸 Недостатньо коштів для розлучення")

    shared -= 500

    a = random.randint(0, shared)
    b = shared - a

    COINS[u] = a
    COINS[p] = b

    MARRIAGES.pop(u)
    MARRIAGES.pop(p)

    save_data()
    update.message.reply_text(
        f"💔 Розлучення завершено\n"
        f"💰 @{u}: {a}\n"
        f"💰 @{p}: {b}"
    )
    
# ================== MAIN ==================
def main():
    load_data()  # 🔥 КРИТИЧНО

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
    dp.add_handler(CommandHandler("buy_ring", buy_ring))
    dp.add_handler(CommandHandler("marry", marry))
    dp.add_handler(CommandHandler("divorce", divorce))

    updater.start_polling()
    updater.idle()

if __name__ == "__main__":
    main()
