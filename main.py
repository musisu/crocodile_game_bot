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
STEAL_BASE_CHANCE = 0.4
STEAL_STEP = 0.2
STEAL_MAX_CHANCE = 0.9
BANK_ROBBERY_CHANCE = 0.05
BANK_ZERO_CHANCE = 0.7
DATA_FILE = "coins.json"

# ================== STORAGE ==================
COINS = {}
MARRIAGES = {}
INVENTORY = {}
PROPOSALS = {}
PENDING_MARRIAGES = {}
DEPOSITS = {}
STEAL_CHANCE = {}

RINGS = {
    "silver": 200,
    "gold": 500,
    "diamond": 1000
}

# ================== DATA HANDLING ==================
def load_data():
    global COINS, MARRIAGES, INVENTORY, PROPOSALS, DEPOSITS
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            COINS = data.get("coins", {})
            MARRIAGES = data.get("marriages", {})
            INVENTORY = data.get("inventory", {})
            PROPOSALS = data.get("proposals", {})
            DEPOSITS = data.get("deposits", {})
    except (FileNotFoundError, json.JSONDecodeError):
        COINS = {}
        MARRIAGES = {}
        INVENTORY = {}
        PROPOSALS = {}
        DEPOSITS = {}

def save_data():
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump({
            "coins": COINS,
            "marriages": MARRIAGES,
            "inventory": INVENTORY,
            "proposals": PROPOSALS,
            "deposits": DEPOSITS
        }, f, ensure_ascii=False, indent=2)

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

# ================== UTILITY ==================
def is_married(username):
    return username in MARRIAGES

def get_shared_balance(username):
    return MARRIAGES[username]["shared"] if is_married(username) else COINS.get(username, 0)

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

def add_coins(username, amount):
    if is_married(username):
        MARRIAGES[username]["shared"] += amount
    else:
        COINS[username] = COINS.get(username, 0) + amount

def is_admin(update, context):
    try:
        member = context.bot.get_chat_member(update.effective_chat.id, update.effective_user.id)
        return member.status in ("administrator", "creator")
    except Exception:
        return False

# ================== WORDS ==================
with open("words.txt", "r", encoding="utf-8") as f:
    WORDS = [w.strip().lower() for w in f.readlines()]
shuffle(WORDS)

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
    if context.chat_data.get("is_playing") and user.id != context.chat_data.get("current_player") and text == context.chat_data.get("current_word"):
        update.message.reply_text(f"{user.first_name} вгадав слово!")
        rating = context.chat_data.setdefault("rating", {})
        rating[username] = rating.get(username, 0) + 1
        pos = sorted(rating.values(), reverse=True).index(rating[username]) + 1
        add_coins(username, TOP_REWARD.get(pos, 0))
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

# ================== WALLET ==================
def wallet(update, context):
    username = update.message.from_user.username or update.message.from_user.first_name
    if is_married(username):
        partner = MARRIAGES[username]["partner"]
        shared = MARRIAGES[username]["shared"]
        update.message.reply_text(f"💑 @{username} у шлюбі з @{partner}\n💰 Спільний баланс: {shared}")
    else:
        balance = COINS.get(username, 0)
        update.message.reply_text(f"@{username}, у вас {balance} монет")
    deposit = DEPOSITS.get(username, 0)
    if deposit > 0:
        update.message.reply_text(f"🏦 Депозит: {deposit} монет")

# ================== COINS COMMANDS ==================
def add_coins_cmd(update, context):
    if not is_admin(update, context):
        return update.message.reply_text("⛔ Тільки адмін")
    if not update.message.reply_to_message or len(context.args) != 1:
        return update.message.reply_text("❗ /add <кількість> (reply)")
    amount = int(context.args[0])
    user = update.message.reply_to_message.from_user
    username = user.username or user.first_name
    add_coins(username, amount)
    save_data()
    update.message.reply_text(f"✅ @{username} +{amount}")

def deduct_coins_cmd(update, context):
    if not is_admin(update, context):
        return update.message.reply_text("⛔ Тільки адмін")
    if not update.message.reply_to_message or len(context.args) != 1:
        return update.message.reply_text("❗ /deduct <кількість> (reply)")
    amount = int(context.args[0])
    user = update.message.reply_to_message.from_user
    username = user.username or user.first_name
    if is_married(username):
        shared = MARRIAGES[username]["shared"]
        if shared < amount:
            return update.message.reply_text("❗ Недостатньо спільного балансу")
        MARRIAGES[username]["shared"] -= amount
    else:
        COINS[username] = max(COINS.get(username,0)-amount,0)
    save_data()
    update.message.reply_text(f"✅ @{username} -{amount}")

def gift_coins(update, context):
    if not update.message.reply_to_message or len(context.args) != 1:
        return update.message.reply_text("❗ /gift <кількість> (reply)")
    try:
        amount = int(context.args[0])
        if amount <= 0: raise ValueError
    except ValueError:
        return update.message.reply_text("❗ Кількість має бути додатнім числом")
    from_user = update.message.from_user
    to_user = update.message.reply_to_message.from_user
    from_name = from_user.username or from_user.first_name
    to_name = to_user.username or to_user.first_name
    balance = get_shared_balance(from_name)
    if balance < amount:
        return update.message.reply_text("💸 Недостатньо монет")
    spend_coins(from_name, amount)
    add_coins(to_name, amount)
    save_data()
    update.message.reply_text(f"🎁 @{from_name} подарував @{to_name} {amount} монет")

# ================== STEAL ==================
def steal_coins(update, context):
    if not update.message.reply_to_message:
        return update.message.reply_text("❗ /steal у відповідь")
    thief = update.message.from_user
    victim = update.message.reply_to_message.from_user
    thief_name = thief.username or thief.first_name
    victim_name = victim.username or victim.first_name
    if thief_name == victim_name:
        return update.message.reply_text("🤨 Сам у себе красти не можна")
    chance = STEAL_CHANCE.get(thief_name, STEAL_BASE_CHANCE)
    if random.random() < chance:
        fine = 50
        spend_coins(thief_name, fine)
        STEAL_CHANCE[thief_name] = STEAL_BASE_CHANCE
        save_data()
        return update.message.reply_text(f"🚓 @{thief_name} попався!\n💸 Штраф {fine} монет\n🔄 Шанс скинуто до 40%")
    steal_amount = random.randint(0,20)
    victim_balance = get_shared_balance(victim_name)
    real_amount = min(steal_amount, victim_balance)
    spend_coins(victim_name, real_amount)
    add_coins(thief_name, real_amount)
    STEAL_CHANCE[thief_name] = min(chance + STEAL_STEP, STEAL_MAX_CHANCE)
    save_data()
    update.message.reply_text(f"🕵️ @{thief_name} поцупив {real_amount} монет у @{victim_name}!\n⚠️ Новий шанс попастися: {int(STEAL_CHANCE[thief_name]*100)}%")

# ================== RINGS & MARRIAGE ==================
def buy_ring(update, context):
    if len(context.args) != 1:
        return update.message.reply_text(f"❗ /buy_ring <тип> | Доступні: {', '.join(RINGS.keys())}")
    ring = context.args[0].lower()
    if ring not in RINGS: return update.message.reply_text("❗ Невірний тип каблучки")
    username = update.message.from_user.username or update.message.from_user.first_name
    price = RINGS[ring]
    if not spend_coins(username, price): return update.message.reply_text("💸 Недостатньо монет")
    INVENTORY.setdefault(username, {"rings":[]})
    INVENTORY[username]["rings"].append(ring)
    save_data()
    update.message.reply_text(f"💍 @{username} купив каблучку {ring}")

def marry(update, context):
    if not update.message.reply_to_message:
        return update.message.reply_text("❗ /marry у відповідь на повідомлення")
    proposer = update.message.from_user
    partner = update.message.reply_to_message.from_user
    proposer_name = proposer.username or proposer.first_name
    partner_name = partner.username or partner.first_name
    if proposer_name in MARRIAGES or partner_name in MARRIAGES:
        return update.message.reply_text("💔 Хтось уже в шлюбі")
    rings = INVENTORY.get(proposer_name, {}).get("rings", [])
    if not rings:
        return update.message.reply_text("❗ Купи каблучку")
    ring = rings[-1]
    PENDING_MARRIAGES[partner_name] = {"from": proposer_name, "ring": ring}
    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("💍 Прийняти", callback_data="marry_accept"), InlineKeyboardButton("❌ Відхилити", callback_data="marry_decline")]])
    update.message.reply_text(f"💌 @{partner_name}, тобі зробили пропозицію!\nКаблучка: {ring}", reply_markup=keyboard)

def marriage_callback(update, context):
    query = update.callback_query
    query.answer()
    username = query.from_user.username or query.from_user.first_name
    if username not in PENDING_MARRIAGES:
        return query.edit_message_text("❌ Пропозиція недійсна")
    data = PENDING_MARRIAGES.pop(username)
    proposer = data["from"]
    ring = data["ring"]
    if query.data == "marry_decline":
        return query.edit_message_text(f"💔 @{username} відхилив пропозицію від @{proposer}")
    shared_balance = COINS.get(username,0) + COINS.get(proposer,0)
    COINS[username] = 0
    COINS[proposer] = 0
    MARRIAGES[username] = {"partner": proposer, "shared": shared_balance}
    MARRIAGES[proposer] = {"partner": username, "shared": shared_balance}
    INVENTORY.setdefault(username, {"rings":[]})
    INVENTORY[username]["rings"].append(ring)
    INVENTORY[proposer]["rings"].remove(ring)
    save_data()
    query.edit_message_text(f"💒 @{username} та @{proposer} одружились!\n💍 Каблучка залишилась у @{username}\n💰 Спільний баланс: {shared_balance}")

def divorce(update, context):
    username = update.message.from_user.username or update.message.from_user.first_name
    if username not in MARRIAGES:
        return update.message.reply_text("❗ Ти не в шлюбі")
    partner = MARRIAGES[username]["partner"]
    shared = MARRIAGES[username]["shared"]
    if shared < 500: return update.message.reply_text("💸 Недостатньо коштів для розлучення")
    shared -= 500
    a = random.randint(0, shared)
    b = shared - a
    COINS[username] = a
    COINS[partner] = b
    MARRIAGES.pop(username)
    MARRIAGES.pop(partner)
    save_data()
    update.message.reply_text(f"💔 Розлучення завершено\n💰 @{username}: {a}\n💰 @{partner}: {b}")

def top_money(update, context):
    if not COINS:
        return update.message.reply_text("Поки що немає монет")

    top = sorted(COINS.items(), key=lambda x: x[1], reverse=True)[:5]
    msg = "\n".join(f"{i+1}. @{u}: {c}" for i, (u, c) in enumerate(top))
    update.message.reply_text(f"💰 Топ монет:\n{msg}")

# ================== MAIN ==================
def main():
    load_data()
    updater = Updater(os.environ["TOKEN"], use_context=True)
    dp = updater.dispatcher

    # Message handler
    dp.add_handler(MessageHandler(Filters.text & ~Filters.command, global_text_handler), group=0)

    # Game conversation
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

    # Commands
    dp.add_handler(CommandHandler("wallet", wallet))
    dp.add_handler(CommandHandler("top_money", top_money))
    dp.add_handler(CommandHandler("top", top_messages))
    dp.add_handler(CommandHandler("add", add_coins_cmd))
    dp.add_handler(CommandHandler("deduct", deduct_coins_cmd))
    dp.add_handler(CommandHandler("gift", gift_coins))
    dp.add_handler(CommandHandler("steal", steal_coins))
    dp.add_handler(CommandHandler("buy_ring", buy_ring))
    dp.add_handler(CommandHandler("marry", marry))
    dp.add_handler(CommandHandler("divorce", divorce))
    dp.add_handler(CallbackQueryHandler(marriage_callback, pattern="^marry_"))
    dp.add_handler(
    MessageHandler(Filters.text & ~Filters.command, global_text_handler),
    group=0
)

    updater.start_polling()
    updater.idle()

if __name__ == "__main__":
    main()
