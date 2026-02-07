#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Sultanov Andriy
"""
import os
from random import shuffle, choice
from datetime import datetime
from telegram import ReplyKeyboardMarkup, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (Updater, CommandHandler, MessageHandler, Filters,
                          ConversationHandler, CallbackQueryHandler)

import logging

# Enable logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    level=logging.INFO)
logger = logging.getLogger(__name__)

GUESSING, CHOOSING_PLAYER = range(2)

# --- Завантажуємо слова ---
WORDS = []
with open("words.txt", "r", encoding="UTF-8", errors="ignore") as file:
    for line in file.readlines():
        WORDS.append(line.strip())
shuffle(WORDS)

# =================== Функції бота ===================

def show_rating(update, context):
    if 'rating' in context.chat_data and context.chat_data['rating']:
        rating = context.chat_data['rating']
        rating = {k: v for k, v in sorted(rating.items(), key=lambda x: x[1][1], reverse=True)}
        text = '\n'.join([f"{i+1}. {item[1][0]}: {item[1][1]} виграші" for i, item in enumerate(rating.items())])
        update.message.reply_text(f"Рейтинг гравців у цьому чаті:\n{text}", parse_mode="Markdown")
    else:
        update.message.reply_text("В цьому чаті не існує рейтингу")

def clear_rating(update, context):
    if 'rating' in context.chat_data and context.chat_data['rating']:
        context.chat_data['rating'] = None
        update.message.reply_text("Я почистив рейтинг")
    else:
        update.message.reply_text("В цьому чаті не існує рейтингу")

def start(update, context):
    if 'is_playing' in context.chat_data and context.chat_data['is_playing']:
        update.message.reply_text("Гра вже почалась")
        return

    logger.info("new game round")

    keyboard = [
        [InlineKeyboardButton("Подивитись слово", callback_data="look"),
         InlineKeyboardButton("Наступне слово", callback_data="next")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    user_data = update['message'].from_user
    first_name = user_data['first_name'] or ""
    last_name = f" {user_data['last_name']}" if user_data['last_name'] else ""
    reply_text = f"[{first_name}{last_name}](tg://user?id={user_data['id']}) пояснює слово!"

    context.chat_data['is_playing'] = True
    context.chat_data['current_player'] = user_data['id']
    context.chat_data['current_word'] = choice(WORDS)
    logger.info(f"Chose the word {context.chat_data['current_word']}")

    update.message.reply_text(reply_text, reply_markup=reply_markup, parse_mode="Markdown")
    return GUESSING

def stop(update, context):
    if context.chat_data.get("is_playing"):
        context.chat_data['current_player'] = None
        context.chat_data['current_word'] = None
        context.chat_data["is_playing"] = False
        update.message.reply_text("Я зупинив гру")
        return CHOOSING_PLAYER
    else:
        update.message.reply_text("Немає гри, яку я можу зупинити")

def guesser(update, context):
    text = update.message.text.lower()
    user_data = update['message'].from_user

    if user_data['id'] != context.chat_data.get("current_player") and text == context.chat_data.get("current_word"):
        rating = context.chat_data.get('rating', {})

        first_name = user_data['first_name'] or ""
        last_name = f" {user_data['last_name']}" if user_data['last_name'] else ""

        if user_data['id'] in rating:
            rating[user_data['id']] = [f"[{first_name}{last_name}](tg://user?id={user_data['id']})",
                                       rating[user_data['id']][1] + 1]
        else:
            rating[user_data['id']] = [f"[{first_name}{last_name}](tg://user?id={user_data['id']})", 1]

        context.chat_data['rating'] = rating
        context.chat_data['winner'] = user_data['id']
        context.chat_data['win_time'] = datetime.now()

        logger.info(f"Player <{user_data['username']}> guessed the word <{context.chat_data['current_word']}>")

        keyboard = [[InlineKeyboardButton("Я хочу пояснювати наступним!", callback_data="next_player")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        reply_text = f"[{first_name}{last_name}](tg://user?id={user_data['id']}) вгадав слово!"
        update.message.reply_text(reply_text, reply_markup=reply_markup, parse_mode="Markdown")

        return CHOOSING_PLAYER
    else:
        logger.info(f"Player <{user_data['username']}> typed <{text}> and did not guess")
        return GUESSING

def next_player(update, context):
    logger.info("Next player")
    query = update.callback_query
    if query.from_user['id'] == context.chat_data.get('winner') or \
       (datetime.now() - context.chat_data.get('win_time', datetime.now())).total_seconds() > 5:

        query.answer()
        keyboard = [
            [InlineKeyboardButton("Подивитись слово", callback_data="look"),
             InlineKeyboardButton("Наступне слово", callback_data="next")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        first_name = query.from_user['first_name'] or ""
        last_name = f" {query.from_user['last_name']}" if query.from_user['last_name'] else ""
        reply_text = f"[{first_name}{last_name}](tg://user?id={query.from_user['id']}) пояснює слово!"

        context.chat_data["current_player"] = query.from_user['id']
        context.chat_data['current_word'] = choice(WORDS)

        query.edit_message_text(text=reply_text, parse_mode="Markdown")
        query.edit_message_reply_markup(reply_markup=reply_markup)
        return GUESSING
    else:
        query.bot.answerCallbackQuery(callback_query_id=query.id,
                                      text="Переможець має 5 секунд на вибір, почекайте",
                                      show_alert=True)

def see_word(update, context):
    query = update.callback_query
    if context.chat_data.get('current_player') == query.from_user['id']:
        query.bot.answerCallbackQuery(callback_query_id=query.id,
                                      text=context.chat_data['current_word'],
                                      show_alert=True)
    else:
        query.bot.answerCallbackQuery(callback_query_id=query.id,
                                      text="Тобі не можна піддивлятися!",
                                      show_alert=True)
    return GUESSING

def next_word(update, context):
    query = update.callback_query
    if context.chat_data.get('current_player') == query.from_user['id']:
        context.chat_data['current_word'] = choice(WORDS)
        query.bot.answerCallbackQuery(callback_query_id=query.id,
                                      text=context.chat_data['current_word'],
                                      show_alert=True)
    else:
        query.bot.answerCallbackQuery(callback_query_id=query.id,
                                      text="Тобі не можна переходити до наступного слова!",
                                      show_alert=True)
    return GUESSING

# =================== НОВА ФУНКЦІЯ ДЛЯ "ГЕТЕРО" ===================
def plate_on_hetero(update, context):
    text = update.message.text.lower()
    if "гетеро" in text:
        update.message.reply_text("🍽️")

# =================== MAIN ===================
def main():
    token = os.environ['TOKEN']
    updater = Updater(token, use_context=True)
    dp = updater.dispatcher

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            CHOOSING_PLAYER: [CallbackQueryHandler(next_player, pattern="^next_player$"),
                              CommandHandler('stop', stop)],
            GUESSING: [MessageHandler(Filters.text, guesser),
                       CallbackQueryHandler(see_word, pattern="^look$"),
                       CallbackQueryHandler(next_word, pattern="^next$")],
        },
        fallbacks=[CommandHandler('start', start), CommandHandler('stop', stop)],
        name="my_conversation",
        per_user=False
    )

    dp.add_handler(CommandHandler('rating', show_rating))
    dp.add_handler(CommandHandler('clear_rating', clear_rating))
    dp.add_handler(conv_handler)

    # --- Додаємо наш хендлер для слова "гетеро" ---
    dp.add_handler(MessageHandler(Filters.text & ~Filters.command, plate_on_hetero))

    updater.start_polling()
    updater.idle()

if __name__ == '__main__':
    main()
