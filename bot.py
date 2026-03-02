import telebot
from telebot import types
import pandas as pd
import os
import threading
from flask import Flask

# Tokeningiz
TOKEN = '6844735110:AAHybqfU2qnfxXuy7MGUG-VxvMWs3aP_5f8'
bot = telebot.TeleBot(TOKEN)
app = Flask(__name__)

DB_FILE = "uzdubgo_baza.csv"

# Bazani yuklash yoki yaratish
def load_data():
    if os.path.exists(DB_FILE):
        return pd.read_csv(DB_FILE)
    else:
        df = pd.DataFrame({
            "Ism": ["Zoom", "Umarbek", "AMIN", "Bexruz", "Komron", "Shabnam", "Kamilla", "Tarjimon", "Feniks"],
            "Ishladi": [1400000, 300000, 200000, 400000, 400000, 200000, 200000, 100000, 2360000],
            "To'landi": [700000, 200000, 150000, 400000, 400000, 100000, 100000, 0, 2360000]
        })
        df.to_csv(DB_FILE, index=False)
        return df

def save_data(df):
    df.to_csv(DB_FILE, index=False)

# Boshlang'ich menyu tugmalari
def main_menu():
    markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    btn1 = types.KeyboardButton("📊 Umumiy Hisobot")
    btn2 = types.KeyboardButton("➕ Pul To'lash")
    btn3 = types.KeyboardButton("👤 Aktyor Qo'shish")
    btn4 = types.KeyboardButton("📝 Yangi Ish Qo'shish")
    markup.add(btn1, btn2, btn3, btn4)
    return markup

@bot.message_handler(commands=['start'])
def start(message):
    bot.send_message(message.chat.id, "🎬 **Uzdubgo Pro** boshqaruv paneliga xush kelibsiz, Shohruxxon!\n\nQuyidagi menyudan kerakli bo'limni tanlang:", reply_markup=main_menu(), parse_mode="Markdown")

# 1. Umumiy hisobot
@bot.message_handler(func=lambda message: message.text == "📊 Umumiy Hisobot")
def show_report(message):
    df = load_data()
    df["Qarz"] = df["Ishladi"] - df["To'landi"]
    
    msg = "📊 **UZDUBGO JORIY HISOBOT**\n--------------------------------\n"
    for _, row in df.iterrows():
        status = "✅" if row["Qarz"] <= 0 else "❌"
        msg += f"{status} **{row['Ism']}**: {row['Qarz']:,} so'm\n"
    
    total_debt = df.loc[df["Ism"] != "Feniks", "Qarz"].sum()
    msg += "--------------------------------\n"
    msg += f"🔴 **Jami tarqatilishi kerak: {total_debt:,} so'm**"
    
    bot.send_message(message.chat.id, msg, parse_mode="Markdown")

# 2. Pul to'lash (Tugmalar orqali)
@bot.message_handler(func=lambda message: message.text == "➕ Pul To'lash")
def choose_actor_for_payment(message):
    df = load_data()
    markup = types.InlineKeyboardMarkup(row_width=3)
    buttons = [types.InlineKeyboardButton(name, callback_data=f"pay_{name}") for name in df['Ism'] if df.loc[df['Ism']==name, 'Ishladi'].values[0] > df.loc[df['Ism']==name, 'To\'landi'].values[0]]
    markup.add(*buttons)
    
    if not buttons:
        bot.send_message(message.chat.id, "✅ Hamma qarzlar uzilgan! To'lanishi kerak bo'lgan aktyor yo'q.")
    else:
        bot.send_message(message.chat.id, "Kimga pul to'layapsiz? (Qarzi borlar ro'yxati):", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("pay_"))
def ask_payment_amount(call):
    actor = call.data.split("_")[1]
    bot.answer_callback_query(call.id)
    msg = bot.send_message(call.message.chat.id, f"💰 **{actor}**ga qancha pul berdingiz? (Faqat raqam yozing)", parse_mode="Markdown")
    bot.register_next_step_handler(msg, process_payment, actor)

def process_payment(message, actor):
    try:
        amount = int(message.text)
        df = load_data()
        df.loc[df["Ism"] == actor, "To'landi"] += amount
        save_data(df)
        
        qarz = df.loc[df["Ism"] == actor, "Ishladi"].values[0] - df.loc[df["Ism"] == actor, "To'landi"].values[0]
        bot.send_message(message.chat.id, f"✅ **Muvaffaqiyatli!**\n\n👤 {actor}ning hisobidan {amount:,} so'm ayirildi.\n📉 Qolgan qarzi: {qarz:,} so'm", parse_mode="Markdown")
    except ValueError:
        bot.send_message(message.chat.id, "⚠️ Xato! Faqat raqam kiriting. Boshidan boshlang.")

# 3. Aktyor qo'shish
@bot.message_handler(func=lambda message: message.text == "👤 Aktyor Qo'shish")
def add_actor_step1(message):
    msg = bot.send_message(message.chat.id, "Yangi aktyorning ismini yozing:")
    bot.register_next_step_handler(msg, add_actor_step2)

def add_actor_step2(message):
    new_name = message.text.capitalize()
    df = load_data()
    
    if new_name in df["Ism"].values:
        bot.send_message(message.chat.id, "⚠️ Bu aktyor ro'yxatda bor!")
        return
        
    new_row = pd.DataFrame({"Ism": [new_name], "Ishladi": [0], "To'landi": [0]})
    df = pd.concat([df, new_row], ignore_index=True)
    save_data(df)
    
    bot.send_message(message.chat.id, f"✅ **{new_name}** ro'yxatga qo'shildi!", parse_mode="Markdown")

# 4. Yangi ish (qarz) qo'shish
@bot.message_handler(func=lambda message: message.text == "📝 Yangi Ish Qo'shish")
def add_work_step1(message):
    df = load_data()
    markup = types.InlineKeyboardMarkup(row_width=3)
    buttons = [types.InlineKeyboardButton(name, callback_data=f"work_{name}") for name in df['Ism']]
    markup.add(*buttons)
    bot.send_message(message.chat.id, "Kimga yangi ish haqi (qarz) qo'shamiz?", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("work_"))
def add_work_step2(call):
    actor = call.data.split("_")[1]
    bot.answer_callback_query(call.id)
    msg = bot.send_message(call.message.chat.id, f"🎬 **{actor}** qancha ishladi? (So'mda yozing)", parse_mode="Markdown")
    bot.register_next_step_handler(msg, process_work, actor)

def process_work(message, actor):
    try:
        amount = int(message.text)
        df = load_data()
        df.loc[df["Ism"] == actor, "Ishladi"] += amount
        save_data(df)
        bot.send_message(message.chat.id, f"✅ **{actor}**ning hisobiga {amount:,} so'm qo'shildi!", parse_mode="Markdown")
    except:
        bot.send_message(message.chat.id, "⚠️ Xato! Boshidan boshlang.")

# Render uchun "Aldamchi" sahifa
@app.route('/')
def index(): return "Uzdubgo Pro is Active!"

def run_bot(): bot.polling(none_stop=True)

if __name__ == "__main__":
    threading.Thread(target=run_bot).start()
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
