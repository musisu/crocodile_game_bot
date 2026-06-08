import os
import json
import random
from datetime import datetime
import pytz

# Налаштування таймзони
KYIV_TZ = pytz.timezone("Europe/Kiev")
STATE_FILE = "world_state.json"

# === НАЗВИ ТА СПИСКИ ===
MOON_PHASES = [
    "Порожній день", "Молодик", "Підріст", "Підповня", 
    "Повня", "Перша щербина", "Остання кварта", "Гнилюк"
]

WEATHER_TYPES = ["ясна", "дощ", "гроза"]

# === РЕАЛЬНА БАЗА КАРТ СВІТУ (БЕЗ СТІКЕРІВ) ===
CARDS_DB = {
    "ліс": {
        "disaster": ["Комарі"],
        "trinket": ["Черепок", "Скарби"],
        "habitat": {
            "6-ка": "Мухомори", "7-ка": "М+М", "8-ка": "Заєць", 
            "9-ка": "Їжак", "10-ка": "Лисиця"
        },
        "chthon": {
            "Паж": "Антипко", "Дама": "Мавка", "Король": "Лісовик", 
            "Туз": "Серп", "Джокер": ["Джокер: Тунде", "Джокер: Аркері"]
        }
    },
    "село": {
        "disaster": ["Гуси (Напали та покусали)"],
        "trinket": ["Стрічка", "Жабка"],
        "habitat": {
            "6-ка": "Буряк", "7-ка": "Склеп", "8-ка": "Курочка", 
            "9-ка": "Собака", "10-ка": "Кіт"
        },
        "chthon": {
            "Паж": "Дідько", "Дама": "Баба", "Король": "Водяник", 
            "Туз": "Монета", "Джокер": ["Джокер: Тунде", "Джокер: Аркері"]
        }
    },
    "поле": {
        "disaster": ["Кропива (Обпік руки)"],
        "trinket": ["Пір'їна", "Ватра"],
        "habitat": {
            "6-ка": "Польові квіти", "7-ка": "Роздвоєна верба", "8-ка": "Кізонька", 
            "9-ка": "Кажан", "10-ка": "Ворон"
        },
        "chthon": {
            "Паж": "Біс", "Дама": "Лала", "Король": "Блуд", 
            "Туз": "Дзеркало", "Джокер": ["Джокер: Тунде", "Джокер: Аркері"]
        }
    },
    "болото": {
        "disaster": ["П'явки"],
        "trinket": ["Чобіт", "Вудка"],
        "habitat": {
            "6-ка": "Росички", "7-ка": "Хижа", "8-ка": "Равлик", 
            "9-ка": "Ропуха", "10-ка": "Блимавки"
        },
        "chthon": {
            "Паж": "Гаспид", "Дама": "Болотяниці", "Король": "Болотяник", 
            "Туз": "Хрест", "Джокер": ["Джокер: Тунде", "Джокер: Аркері"]
        }
    }
}

def load_world_state():
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            pass
    return {"moon_phase_index": 4, "weather": "ясна"}

def save_world_state(state):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)

def update_daily_environment():
    state = load_world_state()
    state["moon_phase_index"] = (state["moon_phase_index"] + 1) % 8
    state["weather"] = random.choices(WEATHER_TYPES, weights=[60, 30, 10], k=1)[0]
    save_world_state(state)
    return state

def get_time_of_day():
    now = datetime.now(KYIV_TZ)
    return "день" if 6 <= now.hour < 18 else "ніч"

def calculate_chances(location, time_of_day):
    state = load_world_state()
    weather = state["weather"]
    moon = MOON_PHASES[state["moon_phase_index"]]

    disaster = 10
    trinket = 30
    habitat = 40
    chthon = 20

    if (location in ["ліс", "болото"] and time_of_day == "ніч") or \
       (location in ["поле", "село"] and time_of_day == "день"):
        chthon += 10
        habitat -= 10

    if weather == "дощ":
        chthon += 5
        habitat -= 5
    elif weather == "гроза":
        chthon += 10
        habitat -= 10

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

    return {
        "disaster": max(0, disaster),
        "trinket": max(0, trinket),
        "habitat": max(0, habitat),
        "chthon": max(0, chthon)
    }

def roll_gacha(location, time_of_day):
    chances = calculate_chances(location, time_of_day)
    categories = ["disaster", "trinket", "habitat", "chthon"]
    weights = [chances["disaster"], chances["trinket"], chances["habitat"], chances["chthon"]]
    
    chosen_cat = random.choices(categories, weights=weights, k=1)[0]
    pool = CARDS_DB[location][chosen_cat]

    if chosen_cat == "disaster":
        card_value = random.choice(pool) if isinstance(pool, list) else pool
        return "Лихо", card_value
    elif chosen_cat == "trinket":
        card_value = random.choice(pool) if isinstance(pool, list) else pool
        return "Дрібничка", card_value
    elif chosen_cat == "habitat":
        sub_cards = ["6-ка", "7-ка", "8-ка", "9-ка", "10-ка"]
        sub_weights = [9, 9, 8, 7, 7]
        chosen_key = random.choices(sub_cards, weights=sub_weights, k=1)[0]
        card_value = pool[chosen_key]
        if isinstance(card_value, list):
            card_value = random.choice(card_value)
        return f"Хабітат ({chosen_key})", card_value
    elif chosen_cat == "chthon":
        sub_cards = ["Паж", "Дама", "Король", "Туз", "Джокер"]
        sub_weights = [6, 5, 5, 3, 100]
        chosen_key = random.choices(sub_cards, weights=sub_weights, k=1)[0]
        card_value = pool[chosen_key]
        if isinstance(card_value, list):
            card_value = random.choice(card_value)
        return f"Хтонь ({chosen_key})", card_value
