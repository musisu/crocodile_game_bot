
import os
import json
import random
from datetime import datetime
import pytz
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

# Налаштування таймзони (як у main.py)
KYIV_TZ = pytz.timezone("Europe/Kiev")
STATE_FILE = "world_state.json"

# === НАЗВИ ТА СПИСКИ ===
MOON_PHASES = [
    "Порожній день", "Молодик", "Підріст", "Підповня", 
    "Повня", "Перша щербина", "Остання кварта", "Гнилюк"
]

WEATHER_TYPES = ["ясна", "дощ", "гроза"]

# === БАЗА КАРТОК (Плейсхолдери) ===
# Коли карти будуть готові, сюди можна буде додати "file_id" для відправки фото.
CARDS_DB = {
    "село": {
        "disaster": ["Оскаженілий півень проклював кишеню", "Місцева ворожка наслала вроки", "Впав у відкритий погріб"],
        "trinket": ["Тріснута підкова", "Старий глиняний глечик", "Жменя домашнього насіння"],
        "habitat": {
            "6-ка": "Солом'яна стріха", "7-ка": "Плетений тин", "8-ка": "Криничний журавель", 
            "9-ка": "Старий млин", "10-ка": "Сільська рада"
        },
        "chthon": {
            "Паж": "Паж Села (Хлопчик-помічник)", "Дама": "Відьма-знахарка", 
            "Король": "Сільський Голова", "Туз": "Дух Оселі (Домовик)", "Джокер": "🎭 Чортик-Вайлуgeneric"
        }
    },
    "поле": {
        "disaster": ["Напекло голову під сонцем", "Вкусила польова миша", "Заблукав у високому житі"],
        "trinket": ["Засушений колосок", "Гладкий камінчик", "Пір'їнка перепела"],
        "habitat": {
            "6-ка": "Волошка", "7-ка": "Степова стежка", "8-ка": "Перекотиполе", 
            "9-ка": "Курган", "10-ка": "Грозове небо над степом"
        },
        "chthon": {
            "Паж": "Паж Поля (Вістун)", "Дама": "Полудниця", 
            "Король": "Степовий Князь", "Туз": "Дух Врожаю", "Джокер": "🎭 Полуденний Чорт"
        }
    },
    "ліс": {
        "disaster": ["Гадюка вкусила за палець", "З'їв отруйну ягоду", "Налякав дикий кабан"],
        "trinket": ["Шишка старого дуба", "Шматочок моху", "Оленячий ріг"],
        "habitat": {
            "6-ка": "Дика папороть", "7-ка": "Грибна галявина", "8-ка": "Лисяча нора", 
            "9-ка": "Криве дерево", "10-ка": "Прадавній дуб"
        },
        "chthon": {
            "Паж": "Паж Лісу (Перелісник)", "Дама": "Мавка Лісова", 
            "Король": "Лісовик", "Туз": "Серце Лісу", "Джокер": "🎭 Прадавній Дідько"
        }
    },
    "болото": {
        "disaster": ["Затягнуло по коліно в багнюку", "Наковтався отруйного газу", "П'явка впилася в ногу"],
        "trinket": ["Річкове латаття", "Жменя торфу", "Стара жаб'яча шкіра"],
        "habitat": {
            "6-ка": "Очерет", "7-ка": "Ряска", "8-ка": "Трясовина", 
            "9-ка": "Гнила колода", "10-ка": "Блукаючий вогник"
        },
        "chthon": {
            "Паж": "Паж Болота (Потерча)", "Дама": "Болотяна Кикимора", 
            "Король": "Водяник", "Туз": "Око Трясовини", "Джокер": "🎭 Болотяний Чорт"
        }
    }
}

# === КЕРУВАННЯ СТАНОМ СВІТУ ===
def load_world_state():
    """Завантажує погоду та місяць із файлу"""
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            pass
    return {"moon_phase_index": 4, "weather": "ясна"}  # Дефолт: Повня, Ясно

def save_world_state(state):
    """Зберігає погоду та місяць у файл"""
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)

def update_daily_environment(context=None):
    """Щоденне ранкове оновлення світу"""
    state = load_world_state()
    
    # 1. Наступна фаза місяця по колу (0-7)
    state["moon_phase_index"] = (state["moon_phase_index"] + 1) % 8
    
    # 2. Нова погода (60% ясна, 30% дощ, 10% гроза)
    state["weather"] = random.choices(WEATHER_TYPES, weights=[60, 30, 10], k=1)[0]
    
    save_world_state(state)
    return state

def get_time_of_day():
    """Визначає час доби за Києвом: день (6-18), ніч (18-6)"""
    now = datetime.now(KYIV_TZ)
    return "день" if 6 <= now.hour < 18 else "ніч"

# === МАТЕМАТИКА ШАНСІВ (ГАЧА) ===
def calculate_chances(location, time_of_day):
    """Обчислює динамічні ваги для 4 основних категорій"""
    state = load_world_state()
    weather = state["weather"]
    moon = MOON_PHASES[state["moon_phase_index"]]

    # Базові відсотки
    disaster = 10
    trinket = 30
    habitat = 40
    chthon = 20

    # 1. Вплив часу доби та локації
    if (location in ["ліс", "болото"] and time_of_day == "ніч") or \
       (location in ["поле", "село"] and time_of_day == "день"):
        chthon += 10
        habitat -= 10

    # 2. Вплив погоди
    if weather == "дощ":
        chthon += 5
        habitat -= 5
    elif weather == "groza":
        chthon += 10
        habitat -= 10

    # 3. Вплив фаз місяця
    if moon == "Порожній день":
        disaster += 5
        trinket += 5
        habitat -= 5
        chthon -= 5
    elif moon in ["Молодик", "Гнилюк"]:
        chthon += 2
        habitat -= 2
    elif moon in ["Підріст", "Остання кварта"]:
        chthon += 5
        habitat -= 5
    elif moon in ["Підповня", "Перша щербина"]:
        chthon += 10
        habitat -= 10
    elif moon == "Повня":
        chthon += 15
        habitat -= 15

    # Страховка від від'ємних значень
    return {
        "disaster": max(0, disaster),
        "trinket": max(0, trinket),
        "habitat": max(0, habitat),
        "chthon": max(0, chthon)
    }

def roll_gacha(location, time_of_day):
    """Визначає категорію та конкретну карту за твоїм балансом"""
    chances = calculate_chances(location, time_of_day)
    
    categories = ["disaster", "trinket", "habitat", "chthon"]
    weights = [chances["disaster"], chances["trinket"], chances["habitat"], chances["chthon"]]
    
    chosen_cat = random.choices(categories, weights=weights, k=1)[0]
    pool = CARDS_DB[location][chosen_cat]

    if chosen_cat == "disaster":
        return "Лихо", random.choice(pool)
        
    elif chosen_cat == "trinket":
        return "Дрібничка", random.choice(pool)
        
    elif chosen_cat == "habitat":
        # Ваги карт всередині Хабітату (Сума = 40)
        sub_cards = ["6-ка", "7-ка", "8-ка", "9-ка", "10-ка"]
        sub_weights = [9, 9, 8, 7, 7]
        chosen_key = random.choices(sub_cards, weights=sub_weights, k=1)[0]
        return f"Хабітат ({chosen_key})", pool[chosen_key]
        
    elif chosen_cat == "chthon":
        # Ваги карт всередині Хтоні (Сума = 20)
        sub_cards = ["Паж", "Дама", "Король", "Туз", "Джокер"]
        sub_weights = [6, 5, 5, 3, 1]
        chosen_key = random.choices(sub_cards, weights=sub_weights, k=1)[0]
        return f"Хтонь ({chosen_key})", pool[chosen_key]

# === TELEGRAM handlers ===
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
    """Обробник інлайн-кнопок крутки"""
    query = update.callback_query
    query.answer()
    
    user = query.from_user
    username = user.username or user.first_name
    location = query.data.split("_")[1]
    
    # Імпортуємо функції та змінні з main.py всередині функції, щоб уникнути circular import
    import main
    
    # Перевірка балансу (враховуючи шлюб)
    user_balance = main.get_shared_balance(username)
    if user_balance < 50:
        query.edit_message_text("❌ У тебе недостатньо монет для мандрівки! Потрібно 50 🪙.")
        return

    # Знімаємо базову вартість крутки
    main.spend_coins(username, 50)
    
    time_of_day = get_time_of_day()
    category_name, card_name = roll_gacha(location, time_of_day)
    
    status_msg = f"🚶‍♂️ @{username} вирушає в мандри: *{location.capitalize()}* ({time_of_day})\n"
    status_msg += "─" * 20 + "\n"

    if "Лихо" in category_name:
        # Штраф за Лихо: знімаємо додаткові 20 монет
        main.spend_coins(username, 20)
        status_msg += f"💀 *ЛИХО!* \n{card_name}.\n\n💸 На додачу ти втрачаєш ще *20 монет* штрафу!"
    else:
        status_msg += f"🃏 Твоя знахідка: *{card_name}*\nКатегорія: _{category_name}_"
        
        # Додаємо картку до інвентаря гравця
        main.INVENTORY.setdefault(username, {})
        main.INVENTORY[username].setdefault("cards", {})
        main.INVENTORY[username]["cards"][card_name] = main.INVENTORY[username]["cards"].get(card_name, 0) + 1

    main.save_data()
    query.edit_message_text(text=status_msg, parse_mode="Markdown")

# === РАНКОВЕ ПОВІДОМЛЕННЯ ===
def send_morning_report(context):
    """Генерує новий день та надсилає красивий звіт у чат логів"""
    import main
    
    state = update_daily_environment()
    moon_phase = MOON_PHASES[state["moon_phase_index"]]
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
        chat_id=main.HASHTAG_LOG_CHAT, 
        text=report, 
        parse_mode="Markdown"
    )
