#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import re 
import json
import random
import cards
from random import shuffle, choice
from datetime import datetime
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from datetime import time
from telegram.ext import (
    Updater, CommandHandler, MessageHandler, Filters,
    ConversationHandler, CallbackQueryHandler
)
import logging
import pytz

# ================== LOGGING ==================
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ================== CONSTANTS ==================
GUESSING, CHOOSING_PLAYER = range(2)
SPECIAL_HASHTAG_CHAT = -1002250842606  # чат, де активні хештеги
HASHTAG_LOG_CHAT = -1002408227652      # чат, куди слати повідомлення про бонус
HASHTAG_REWARD = 50
TOP_REWARD = {1: 20, 2: 10, 3: 5}
STEAL_BASE_CHANCE = 0.4
STEAL_STEP = 0.2
STEAL_MAX_CHANCE = 0.9
DEPOSIT_INTEREST = 0.05
BANK_ROBBERY_CHANCE = 0.05
BANK_ROBBERY_LOSS_CHANCE = 0.5
KYIV_TZ = pytz.timezone("Europe/Kiev")
WITHDRAWAL_DAYS = [0, 3]  # 0 = понеділок, 3 = четвер
DATA_FILE = "coins.json"

# ================== STORAGE ==================
COINS = {}
MARRIAGES = {}
INVENTORY = {}
PROPOSALS = {}
PENDING_MARRIAGES = {}
DEPOSITS = {}
STEAL_CHANCE = {}

MESSAGE_STATS = {}
MESSAGE_COUNT = 0

# Структура для підрахунку постів
POST_STATS = {
    "daily": {},    # {"username": count}
    "weekly": {},
    "monthly": {},
    "all_time": {}
}

# Загальна кількість постів
POST_COUNTS = {
    "daily": 0,
    "weekly": 0,
    "monthly": 0,
    "all_time": 0
}

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
    except (FileNotFoundError, json.JSONDecodeError ):
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

    text = update.message.text
    user = update.message.from_user
    username = user.username or user.first_name

    # 📝 Щоденна статистика повідомлень
    global MESSAGE_STATS, MESSAGE_COUNT
    MESSAGE_STATS[username] = MESSAGE_STATS.get(username, 0) + 1
    MESSAGE_COUNT += 1

    # 👹 "гетеро"
    if "гетеро" in text.lower():
        COINS[username] = max(COINS.get(username, 0) - 1, 0)
        save_data()
        update.message.reply_text("👹")
        update.message.reply_text(f"@{username}, -1 монета")

    # ================= HASH LOGIC =================
    if update.message.chat.id == SPECIAL_HASHTAG_CHAT:
        # знайти всі хештеги в тексті
        hashtags = re.findall(r"#\w+", text)
        if hashtags:
            COINS[username] = COINS.get(username, 0) + HASHTAG_REWARD
            save_data()

            try:
                context.bot.send_message(
                    chat_id=HASHTAG_LOG_CHAT,
                    text=f"🎉 @{username} отримав(ла) {HASHTAG_REWARD} монет за хештеги: {' '.join(hashtags)}"
                )
            except Exception as e:
                print(f"Помилка лог-чату: {e}")

            # 📊 Статистика постів
            for period in ["daily", "weekly", "monthly", "all_time"]:
                POST_STATS.setdefault(period, {})
                POST_STATS[period][username] = POST_STATS[period].get(username, 0) + 1
                POST_COUNTS[period] += 1
        save_data()
#=================DEPOSITS===================

def deposit_balance(update, context):
    username = update.message.from_user.username or update.message.from_user.first_name
    balance = DEPOSITS.get(username, 0)
    update.message.reply_text(f"🏦 @{username}, ваш депозит: {balance} монет")

def deposit_add(update, context):
    username = update.message.from_user.username or update.message.from_user.first_name

    if len(context.args) != 1:
        return update.message.reply_text("❗ Використання: /deposit_add <сума>")

    try:
        amount = int(context.args[0])
        if amount <= 0:
            raise ValueError
    except ValueError:
        return update.message.reply_text("❗ Сума має бути додатнім числом")

    if COINS.get(username, 0) < amount:
        return update.message.reply_text("💸 Недостатньо монет для депозиту")

        # шанс пограбування
    if random.random() < BANK_ROBBERY_CHANCE:
        robbed = False
        for user, bal in DEPOSITS.items():
            if bal > 0 and random.random() < BANK_ROBBERY_LOSS_CHANCE:
                DEPOSITS[user] = 0
                robbed = True
        save_data()
        if robbed:
            return update.message.reply_text("💥 Банк пограбували! Частина депозитів обнулилася")

    COINS[username] -= amount
    DEPOSITS[username] = DEPOSITS.get(username, 0) + amount
    save_data()
    update.message.reply_text(f"🏦 @{username} додав {amount} монет на депозит")

def deposit_withdraw(update, context):
    username = update.message.from_user.username or update.message.from_user.first_name
    today = datetime.today().weekday()

    if today not in WITHDRAWAL_DAYS:
        return update.message.reply_text(
            "❌ Вивід депозиту доступний тільки в понеділок та четвер"
        )

    if len(context.args) != 1:
        return update.message.reply_text("❗ Використання: /deposit_withdraw <сума>")

    try:
        amount = int(context.args[0])
        if amount <= 0:
            raise ValueError
    except ValueError:
        return update.message.reply_text("❗ Сума має бути додатнім числом")

    current_deposit = DEPOSITS.get(username, 0)

    if current_deposit <= 0:
        return update.message.reply_text("❌ У вас немає депозиту")

    if amount > current_deposit:
        return update.message.reply_text("❌ На депозиті недостатньо коштів")

    # шанс пограбування
    if random.random() < BANK_ROBBERY_CHANCE:
        robbed = False
        for user, bal in DEPOSITS.items():
            if bal > 0 and random.random() < BANK_ROBBERY_LOSS_CHANCE:
                DEPOSITS[user] = 0
                robbed = True
        save_data()
        if robbed:
            return update.message.reply_text(
                "💥 Банк пограбували! Частина депозитів обнулилася"
            )

    # зняття
    DEPOSITS[username] -= amount
    COINS[username] = COINS.get(username, 0) + amount

    save_data()

    update.message.reply_text(
        f"🏦 @{username} зняв {amount} монет\n"
        f"💰 Залишок депозиту: {DEPOSITS[username]}"
    )

def deposit_daily_interest(context):
    """Функція для щоденного нарахування 5% від депозиту"""
    for user, bal in DEPOSITS.items():
        if bal > 0:
            interest = int(bal * DEPOSIT_INTEREST)
            DEPOSITS[user] += interest
    save_data()

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

def send_daily_message_stats(context):
    global MESSAGE_STATS, MESSAGE_COUNT

    if not MESSAGE_STATS:
        context.bot.send_message(
            chat_id=HASHTAG_LOG_CHAT,
            text="📊 За сьогодні не було повідомлень"
        )
        return

    sorted_users = sorted(
        MESSAGE_STATS.items(),
        key=lambda x: x[1],
        reverse=True
    )

    msg = "📊 Топ повідомлень за день:\n\n"

    rewards = {0: 25, 1: 15, 2: 5}

    for i, (user, count) in enumerate(sorted_users[:5]):
        msg += f"{i+1}. @{user}: {count}\n"

        # Нарахування бонусів топ-3
        if i in rewards:
            bonus = rewards[i]
            COINS[user] = COINS.get(user, 0) + bonus
            msg += f"   💰 +{bonus} монет\n"

    msg += f"\nВсього повідомлень: {MESSAGE_COUNT}"

    context.bot.send_message(chat_id=HASHTAG_LOG_CHAT, text=msg)

    # Обнулення на новий день
    MESSAGE_STATS = {}
    MESSAGE_COUNT = 0

    save_data()

def top_messages(update, context):
    if not MESSAGE_STATS:
        return update.message.reply_text("Немає статистики за сьогодні")

    top = sorted(MESSAGE_STATS.items(), key=lambda x: x[1], reverse=True)[:5]

    msg = "\n".join(
        f"{i+1}. @{u}: {c}"
        for i, (u, c) in enumerate(top)
    )

    update.message.reply_text(f"📝 Топ сьогодні:\n\n{msg}")

def post_stats_report(update, context):
    username = update.message.from_user.username or update.message.from_user.first_name

    msg = "📊 Статистика постів:\n\n"
    for period in ["daily", "weekly", "monthly", "all_time"]:
        top_users = sorted(POST_STATS.get(period, {}).items(), key=lambda x: x[1], reverse=True)[:5]
        top_text = "\n".join([f"{i+1}. @{u}: {c}" for i, (u, c) in enumerate(top_users)]) or "немає постів"
        total = POST_COUNTS.get(period, 0)
        msg += f"📅 {period.capitalize()} — всього постів: {total}\n{top_text}\n\n"

    update.message.reply_text(msg)

#===================STATS=====================

def send_daily_stats(context):
    msg = format_post_stats("daily")
    context.bot.send_message(HASHTAG_LOG_CHAT, msg)
    # обнуляємо лічильку на новий день
    POST_STATS["daily"] = {}
    POST_COUNTS["daily"] = 0

def send_weekly_stats(context):
    msg = format_post_stats("weekly")
    context.bot.send_message(HASHTAG_LOG_CHAT, msg)
    POST_STATS["weekly"] = {}
    POST_COUNTS["weekly"] = 0

def send_monthly_stats(context):
    msg = format_post_stats("monthly")
    context.bot.send_message(HASHTAG_LOG_CHAT, msg)
    POST_STATS["monthly"] = {}
    POST_COUNTS["monthly"] = 0

def format_post_stats(period):
    top_users = sorted(POST_STATS.get(period, {}).items(), key=lambda x: x[1], reverse=True)[:5]
    top_text = "\n".join([f"{i+1}. @{u}: {c}" for i, (u, c) in enumerate(top_users)]) or "немає постів"
    total = POST_COUNTS.get(period, 0)
    msg = f"📊 Статистика постів ({period.capitalize()}):\n\n{top_text}\n\nВсього постів: {total}"
    return msg

# ================== РАНКОВІ ЗВІТИ ==================
def send_morning_report(context):
    """Автоматичний звіт о 08:00: ОНОВЛЮЄ погоду та місяць на новий день"""
    state = cards.update_daily_environment()
    moon_phase = cards.MOON_PHASES[state["moon_phase_index"]]
    weather = state["weather"]
    
    weather_emojis = {"ясна": "☀️ Ясна погода", "дощ": "🌧 Проливний дощ", "гроза": "⛈ Лютнева гроза"}
    moon_emojis = {
        "Порожній день": "🌑 Порожній день (Час лиха)",
        "Молодик": "🌒 Молодик", "Підріст": "🌓 Підріст", "Підповня": "🌔 Підповня",
        "Повня": "🌕 Повня (Пік містики)",
        "Перша щербина": "🌖 Перша щербина", "Остання кварта": "🌗 Остання кварта", "Гнилюк": "🌘 Гнилюк"
    }

    report = (
        f"🌅 *Доброго ранку, чортенята! Новий день настав.*\n\n"
        f"🌙 *Фаза місяця:* {moon_emojis.get(moon_phase, moon_phase)}\n"
        f"🌤 *Погода на день:* {weather_emojis.get(weather, weather)}\n\n"
        f"🔮 _Шанси в локаціях змінилися. Обирайте час для подорожей розумно через /travel_"
    )
    
    context.bot.send_message(
        chat_id=HASHTAG_LOG_CHAT, 
        text=report, 
        parse_mode="Markdown"
    )

def manual_morning_report(update, context):
    """Ручний виклик звіту командою: просто ПОКАЗУЄ поточний стан"""
    state = cards.load_world_state()
    moon_phase = cards.MOON_PHASES[state["moon_phase_index"]]
    weather = state["weather"]
    
    weather_emojis = {"ясна": "☀️ Ясна погода", "дощ": "🌧 Проливний дощ", "гроза": "⛈ Лютнева гроза"}
    moon_emojis = {
        "Порожній день": "🌑 Порожній день (Час лиха)",
        "Молодик": "🌒 Молодик", "Підріст": "🌓 Підріст", "Підповня": "🌔 Підповня",
        "Повня": "🌕 Повня (Пік містики)",
        "Перша щербина": "🌖 Перша щербина", "Остання кварта": "🌗 Остання кварта", "Гнилюк": "🌘 Гнилюк"
    }

    report = (
        f"📊 *Поточний стан світу (Ранковий звіт):*\n\n"
        f"🌙 *Фаза місяця:* {moon_emojis.get(moon_phase, moon_phase)}\n"
        f"🌤 *Погода:* {weather_emojis.get(weather, weather)}\n\n"
        f"🔮 _Значення залишаються незмінними до наступного автоматичного ранку._"
    )
    
    update.message.reply_text(report, parse_mode="Markdown")

# ================== КАРТКОВА ГАЧА-СИСТЕМА ==================
def travel_command(update, context):
    """Команда /travel — відкриває меню локацій"""
    keyboard = [
        [InlineKeyboardButton("🐸 Зазирнути на болото (50 🪙)", callback_data="gacha_болото")],
        [InlineKeyboardButton("🌲 Піти в ліс (50 🪙)", callback_data="gacha_ліс")],
        [InlineKeyboardButton("🌾 Вийти в поле (50 🪙)", callback_data="gacha_поле")],
        [InlineKeyboardButton("🏡 Завітати в село (50 🪙)", callback_data="gacha_село")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    update.message.reply_text(
        "🔮 Куди вирушимо на пошуки пригод та прадавньої хтоні?\n"
        "Кожна мандрівка коштує *50 монет*.", 
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )
def gacha_button_handler(update, context):
    """Обробник інлайн-кнопок крутки з розумним перехопленням джокерів"""
    query = update.callback_query
    
    # ЗАХИСТ ВІД ПОДВІЙНИХ КЛІКІВ
    try:
        query.edit_message_reply_markup(reply_markup=None)
    except Exception:
        query.answer("⌛ Шукаю картку, зачекай...", show_alert=False)
        return

    query.answer()
    
    user = query.from_user
    username = user.username or user.first_name
    location = query.data.split("_")[1]
    
    user_balance = get_shared_balance(username)
    if user_balance < 50:
        query.edit_message_text("❌ У тебе недостатньо монет для мандрівки! Потрібно 50 🪙.")
        return

    spend_coins(username, 50)
    
    time_of_day = cards.get_time_of_day()
    category_name, card_name = cards.roll_gacha(location, time_of_day)
    
    # Маппінг стандартних локацій на папки-масті
    suit_mapping = {
        "болото": "♦️ Болото (Бубна)",
        "ліс": "♠️ Ліс (Піка)",
        "поле": "♣️ Поле (Хреста)",
        "село": "♥️ Село (Черва)"
    }
    
    # Визначаємо початкове ім'я папки
    folder_name = suit_mapping.get(location.lower(), f"📂 {location.capitalize()}")

    status_msg = f"🚶‍♂️ @{username} вирушає в мандри: <b>{location.capitalize()}</b> ({time_of_day})\n"
    status_msg += "─" * 20 + "\n"

    if "Лихо" in category_name:
        spend_coins(username, 20)
        status_msg += f"💀 <b>ЛИХО!</b> \n{card_name}.\n\n💸 На додачу ти втрачаєш ще <b>20 монет</b> штрафу!"
        
    elif "дрібничк" in category_name.lower():
        # Дрібнички ігноруємо
        status_msg += f"🪨 Знахідка: <b>{card_name}</b>\n<i>(Це дрібничка, вона не йде до альбому)</i>"
        
    else:
        # ПЕРЕВІРКА НА ДЖОКЕРА: Якщо в назві карти чи категорії є слово "джокер"
        if "джокер" in category_name.lower() or "джокер" in card_name.lower():
            folder_name = "🃏 Особливі (Джокери)"
            status_msg += f"🃏 <b>ОГО! ТИ ЗНАЙШЛА ДЖОКЕРА!</b> \nТвоя суперрідкісна знахідка: <b>{card_name}</b>"
        else:
            status_msg += f"🃏 Твоя знахідка: <b>{card_name}</b>\nКатегорія: <i>{category_name}</i>"
        
        # Зберігаємо у правильну папку
        INVENTORY.setdefault(username, {})
        INVENTORY[username].setdefault("collections", {})
        INVENTORY[username]["collections"].setdefault(folder_name, {})
        INVENTORY[username]["collections"][folder_name][card_name] = INVENTORY[username]["collections"][folder_name].get(card_name, 0) + 1

    save_data()
    query.edit_message_text(text=status_msg, parse_mode="HTML")


# ================== АНКЕТА ГРАВЦЯ ==================
def profile_command(update, context):
    """Виводить загальну інформацію про гравця"""
    user = update.message.from_user
    username = user.username or user.first_name
    
    if is_married(username):
        partner = MARRIAGES[username]["partner"]
        balance = MARRIAGES[username]["shared"]
        status = f"💍 У шлюбі з @{partner}"
    else:
        balance = COINS.get(username, 0)
        status = "💔 В активному пошуку"
        
    deposit = DEPOSITS.get(username, 0)
    
    rings = INVENTORY.get(username, {}).get("rings", [])
    rings_text = ", ".join(rings) if rings else "Немає"
    
    collections = INVENTORY.get(username, {}).get("collections", {})
    total_cards = sum(sum(cat.values()) for cat in collections.values()) if collections else 0
    unique_cards = sum(len(cat) for cat in collections.values()) if collections else 0
    
    steal_chance = STEAL_CHANCE.get(username, STEAL_BASE_CHANCE)
    steal_percent = int(steal_chance * 100)
    
    profile_text = (
        f"👤 <b>Анкета гравця @{username}</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"❤️ <b>Статус:</b> {status}\n"
        f"💰 <b>Баланс:</b> {balance} 🪙\n"
        f"🏦 <b>Депозит:</b> {deposit} 🪙\n\n"
        f"💍 <b>Каблучки:</b> {rings_text}\n"
        f"🃏 <b>Альбом:</b> {total_cards} знахідок ({unique_cards} унікальних)\n"
        f"🕵️‍♂️ <b>Ризик крадіжки:</b> {steal_percent}% шанс попастися\n"
    )
    update.message.reply_text(profile_text, parse_mode="HTML")


# ================== АЛЬБОМ ТА ІЛЮСТРАЦІЇ ==================
CARD_IMAGES = {}

# Точна кількість унікальних карт для кожної масті за твоїми правилами
MAX_CARDS = {
    "♦️ Болото (Бубна)": 9,
    "♠️ Ліс (Піка)": 9,
    "♣️ Поле (Хреста)": 9,
    "♥️ Село (Черва)": 9,
    "🃏 Особливі (Джокери)": 2  # Додаємо джокерів як окрему приховану колекцію
}
# Загальний максимум гри (4 масті по 9 карт + 2 джокери = 38)
TOTAL_GAME_MAX = 38

def album_command(update, context):
    """Головне меню альбому з прогресом збору за твоїми точними цифрами"""
    username = update.message.from_user.username or update.message.from_user.first_name
    collections = INVENTORY.get(username, {}).get("collections", {})
    valid_cats = sorted(list(collections.keys()))

    if not valid_cats:
        return update.message.reply_text("📖 Твій альбом порожній. Вирушай у /travel!")

    keyboard = []
    total_album_cards = 0      # Всього вибито карт (з повторками)
    total_unique_cards = 0     # Скільки унікальних мастей зібрано
    
    suit_counts = {
        "♦️ Болото (Бубна)": 0,
        "♠️ Ліс (Піка)": 0,
        "♣️ Поле (Хреста)": 0,
        "♥️ Село (Черва)": 0,
        "🃏 Особливі (Джокери)": 0
    }

    for idx, cat_name in enumerate(valid_cats):
        cat_total = sum(collections[cat_name].values())
        cat_unique = len(collections[cat_name])
        
        total_album_cards += cat_total
        total_unique_cards += cat_unique
        
        if cat_name in suit_counts:
            suit_counts[cat_name] = cat_unique

        max_in_cat = MAX_CARDS.get(cat_name, "?")
        btn_text = f"{cat_name} ({cat_unique}/{max_in_cat})"
        keyboard.append([InlineKeyboardButton(btn_text, callback_data=f"alb_cat_{idx}")])

    stats_text = (
        f"♦️ <b>Бубна (Болото):</b> {suit_counts['♦️ Болото (Бубна)']}/{MAX_CARDS['♦️ Болото (Бубна)']} шт.\n"
        f"♠️ <b>Піка (Ліс):</b> {suit_counts['♠️ Ліс (Піка)']}/{MAX_CARDS['♠️ Ліс (Піка)']} шт.\n"
        f"♣️ <b>Хреста (Поле):</b> {suit_counts['♣️ Поле (Хреста)']}/{MAX_CARDS['♣️ Поле (Хреста)']} шт.\n"
        f"♥️ <b>Черва (Село):</b> {suit_counts['♥️ Село (Черва)']}/{MAX_CARDS['♥️ Село (Черва)']} шт."
    )
    
    # Якщо гравець уже знайшов хоча б одного джокера — додаємо його в статистику тексту
    if suit_counts["🃏 Особливі (Джокери)"] > 0:
        stats_text += f"\n🃏 <b>Джокери:</b> {suit_counts['🃏 Особливі (Джокери)']}/{MAX_CARDS['🃏 Особливі (Джокери)']} шт."

    msg_text = (
        f"📖 <b>Твій Альбом Знахідок</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"🏆 <b>Зібрано унікальних:</b> {total_unique_cards} / {TOTAL_GAME_MAX}\n"
        f"📦 <b>Всього карт у тебе (з повторками):</b> {total_album_cards}\n\n"
        f"📊 <b>Прогрес колекцій:</b>\n"
        f"{stats_text}\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"Обери розділ для перегляду карт:"
    )

    update.message.reply_text(msg_text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")


def album_view_handler(update, context):
    """Обробляє навігацію всередині папок альбому"""
    query = update.callback_query
    query.answer()

    username = query.from_user.username or query.from_user.first_name
    collections = INVENTORY.get(username, {}).get("collections", {})
    valid_cats = sorted(list(collections.keys()))
    data = query.data

    # --- 1. ПОВЕРНЕННЯ В ГОЛОВНЕ МЕНЮ ---
    if data == "alb_main":
        keyboard = []
        total_album_cards = 0
        total_unique_cards = 0
        
        suit_counts = {
            "♦️ Болото (Бубна)": 0,
            "♠️ Ліс (Піка)": 0,
            "♣️ Поле (Хреста)": 0,
            "♥️ Село (Черва)": 0,
            "🃏 Особливі (Джокери)": 0
        }

        for idx, cat_name in enumerate(valid_cats):
            cat_total = sum(collections[cat_name].values())
            cat_unique = len(collections[cat_name])
            
            total_album_cards += cat_total
            total_unique_cards += cat_unique
            
            if cat_name in suit_counts:
                suit_counts[cat_name] = cat_unique
            
            max_in_cat = MAX_CARDS.get(cat_name, "?")
            btn_text = f"{cat_name} ({cat_unique}/{max_in_cat})"
            keyboard.append([InlineKeyboardButton(btn_text, callback_data=f"alb_cat_{idx}")])

        stats_text = (
            f"♦️ <b>Бубна (Болото):</b> {suit_counts['♦️ Болото (Бубна)']}/{MAX_CARDS['♦️ Болото (Бубна)']} шт.\n"
            f"♠️ <b>Піка (Ліс):</b> {suit_counts['♠️ Ліс (Піка)']}/{MAX_CARDS['♠️ Ліс (Піка)']} шт.\n"
            f"♣️ <b>Хреста (Поле):</b> {suit_counts['♣️ Поле (Хреста)']}/{MAX_CARDS['♣️ Поле (Хреста)']} шт.\n"
            f"♥️ <b>Черва (Село):</b> {suit_counts['♥️ Село (Черва)']}/{MAX_CARDS['♥️ Село (Черва)']} шт."
        )
        
        if suit_counts["🃏 Особливі (Джокери)"] > 0:
            stats_text += f"\n🃏 <b>Джокери:</b> {suit_counts['🃏 Особливі (Джокери)']}/{MAX_CARDS['🃏 Особливі (Джокери)']} шт."

        msg_text = (
            f"📖 <b>Твій Альбом Знахідок</b>\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"🏆 <b>Зібрано унікальних:</b> {total_unique_cards} / {TOTAL_GAME_MAX}\n"
            f"📦 <b>Всього карт у тебе (з повторками):</b> {total_album_cards}\n\n"
            f"📊 <b>Прогрес колекцій:</b>\n"
            f"{stats_text}\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"Обери розділ для перегляду карт:"
        )
        
        if query.message.photo:
            query.message.delete()
            context.bot.send_message(chat_id=query.message.chat_id, text=msg_text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")
        else:
            query.edit_message_text(text=msg_text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")
        return

    # --- 2. ВІДКРИТТЯ ПАПКИ-МАСТІ ---
    if data.startswith("alb_cat_"):
        cat_idx = int(data.split("_")[2])
        if cat_idx >= len(valid_cats):
            return query.edit_message_text("❌ Помилка. Відкрий альбом знову.")
        
        cat_name = valid_cats[cat_idx]
        cards_in_cat = collections[cat_name]
        card_names = sorted(list(cards_in_cat.keys()))

        keyboard = []
        row = []
        for c_idx, c_name in enumerate(card_names):
            count = cards_in_cat[c_name]
            btn_text = f"{c_name} (x{count})"
            row.append(InlineKeyboardButton(btn_text, callback_data=f"alb_item_{cat_idx}_{c_idx}"))
            if len(row) == 2:
                keyboard.append(row)
                row = []
        if row:
            keyboard.append(row)
        
        keyboard.append([InlineKeyboardButton("⬅️ Назад до розділів", callback_data="alb_main")])

        max_in_cat = MAX_CARDS.get(cat_name, "?")
        msg_text = (
            f"🗂 <b>Розділ: {cat_name}</b>\n"
            f"📈 Прогрес масті: {len(card_names)}/{max_in_cat} унікальних\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"Обери карту, щоб роздивитися її:"
        )

        if query.message.photo:
            query.message.delete()
            context.bot.send_message(chat_id=query.message.chat_id, text=msg_text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")
        else:
            query.edit_message_text(text=msg_text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")
        return

    # --- 3. ПЕРЕГЛЯД КОНКРЕТНОЇ КАРТКИ ---
    if data.startswith("alb_item_"):
        parts = data.split("_")
        cat_idx = int(parts[2])
        card_idx = int(parts[3])

        if cat_idx >= len(valid_cats):
            return query.edit_message_text("❌ Помилка. Відкрий альбом знову.")
        
        cat_name = valid_cats[cat_idx]
        card_names = sorted(list(collections[cat_name].keys()))

        if card_idx >= len(card_names):
            return query.edit_message_text("❌ Помилка. Відкрий альбом знову.")

        card_name = card_names[card_idx]
        count = collections[cat_name][card_name]
        image_id = CARD_IMAGES.get(card_name)

        text = (
            f"🖼 <b>{card_name}</b>\n"
            f"🗂 Знайдено у: <i>{cat_name}</i>\n"
            f"📦 Кількість: <b>{count} шт.</b> (повторки)\n\n"
            f"<i>(Тут згодом з'явиться справжня ілюстрація)</i>"
        )
        
        back_markup = InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Назад до списку", callback_data=f"alb_cat_{cat_idx}")]])

        if image_id:
            try: query.message.delete()
            except Exception: pass
            context.bot.send_photo(
                chat_id=query.message.chat_id, 
                photo=image_id, 
                caption=text, 
                reply_markup=back_markup, 
                parse_mode="HTML"
            )
        else:
            if query.message.photo:
                query.message.delete()
                context.bot.send_message(chat_id=query.message.chat_id, text=text, reply_markup=back_markup, parse_mode="HTML")
            else:
                query.edit_message_text(text=text, reply_markup=back_markup, parse_mode="HTML")

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

    from datetime import timedelta

    # ... після ініціалізації updater
    job_queue = updater.job_queue

    # Ранковий звіт про погоду та фазу місяця о 08:00 за Києвом
    job_queue.run_daily(send_morning_report, time=time(hour=8, minute=0, tzinfo=KYIV_TZ))

    # Щодня о 00:00 київського часу
    job_queue.run_daily(send_daily_stats, time=time(hour=23, minute=59, tzinfo=KYIV_TZ))

    # Щопонеділка о 06:00 київського часу
    job_queue.run_daily(send_weekly_stats, time=time(hour=6, minute=0, tzinfo=KYIV_TZ), days=(0,))  # Monday=0

    # Першого числа місяця о 10:00 київського часу
    job_queue.run_monthly(send_monthly_stats, when=time(hour=10, minute=0, tzinfo=KYIV_TZ), day=1)

    job_queue.run_daily(deposit_daily_interest, time=time(hour=0, minute=0, tzinfo=KYIV_TZ))

    job_queue.run_daily(send_daily_message_stats, time=time(hour=0, minute=0, tzinfo=KYIV_TZ))

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
    dp.add_handler(CommandHandler("deposit_balance", deposit_balance))
    dp.add_handler(CommandHandler("deposit_add", deposit_add))
    dp.add_handler(CommandHandler("deposit_withdraw", deposit_withdraw))
    dp.add_handler(CommandHandler("post_stats_report", post_stats_report))
    dp.add_handler(CallbackQueryHandler(marriage_callback, pattern="^marry_"))
    # Модуль гача-карток
    dp.add_handler(CommandHandler("travel", travel_command))
    dp.add_handler(CallbackQueryHandler(gacha_button_handler, pattern="^gacha_"))
    dp.add_handler(CommandHandler("morning_report", manual_morning_report))
    # Модуль альбому
    dp.add_handler(CommandHandler("album", album_command))
    dp.add_handler(CallbackQueryHandler(album_view_handler, pattern="^alb_"))
        # Профіль гравця
    dp.add_handler(CommandHandler("profile", profile_command))
    dp.add_handler(CommandHandler("me", profile_command)) # Додаємо синонім для зручності

    updater.start_polling()
    updater.idle()

if __name__ == "__main__":
    main()
