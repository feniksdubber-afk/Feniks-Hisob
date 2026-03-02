import telebot
from telebot import types
import pandas as pd
import os
import threading
from flask import Flask

TOKEN = '6844735110:AAHybqfU2qnfxXuy7MGUG-VxvMWs3aP_5f8'
bot = telebot.TeleBot(TOKEN)
app = Flask(__name__)

# Ma'lumotlar bazasi (Buni keyinchalik SQL'ga o'tkazish mumkin)
projects = ["Gravity Falls", "LTC", "Sin Mu", "The Looney Tunes Show"]
actors = ["Zoom", "Umarbek", "AMIN", "Bexruz", "Komron", "Shabnam", "Kamilla", "Tarjimon", "Feniks"]

# Boshlang'ich menyu
def main_menu():
    markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    btn1 = types.KeyboardButton("📊 Umumiy Hisobot")
    btn2 = types.KeyboardButton("📁 Loyihalar")
    btn3 = types.KeyboardButton("➕ Pul To'lash")
    btn4 = types.KeyboardButton("👤 Aktyor Qo'shish")
    markup.add(btn1, btn2, btn3, btn4)
    return markup

@bot.message_handler(commands=['start'])
def start(message):
    bot.send_message(message.chat.id, "🎬 Uzdubgo Pro tizimiga xush kelibsiz!", reply_markup=main_menu())

@bot.message_handler(func=lambda message: message.text == "📁 Loyihalar")
def show_projects(message):
    markup = types.InlineKeyboardMarkup()
    for p in projects:
        markup.add(types.InlineKeyboardButton(p, callback_data=f"project_{p}"))
    bot.send_message(message.chat.id, "Loyihani tanlang:", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("project_"))
def project_details(call):
    p_name = call.data.split("_")[1]
    bot.answer_callback_query(call.id)
    bot.send_message(call.message.chat.id, f"📂 Loyiha: {p_name}\nBu yerda qismlar va aktyorlar narxi chiqadi (Hali sozlanmagan).")

@bot.message_handler(func=lambda message: message.text == "➕ Pul To'lash")
def choose_actor(message):
    markup = types.InlineKeyboardMarkup()
    for a in actors:
        markup.add(types.InlineKeyboardButton(a, callback_data=f"pay_{a}"))
    bot.send_message(message.chat.id, "Kimga pul berdingiz?", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("pay_"))
def ask_amount(call):
    actor = call.data.split("_")[1]
    msg = bot.send_message(call.message.chat.id, f"💰 {actor}ga qancha pul berdingiz? (Faqat raqam yozing)")
    bot.register_next_step_handler(msg, process_payment, actor)

def process_payment(message, actor):
    try:
        amount = int(message.text)
        # Bu yerda bazani yangilash kodi bo'ladi
        bot.send_message(message.chat.id, f"✅ {actor}ga {amount:,} so'm kiritildi!", reply_markup=main_menu())
    except:
        bot.send_message(message.chat.id, "⚠️ Xato! Faqat raqam kiriting.")

# Render uchun soxta port
@app.route('/')
def index(): return "Uzdubgo Pro is Active!"

def run_bot(): bot.polling()

if __name__ == "__main__":
    threading.Thread(target=run_bot).start()
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
    
