import telebot
from telebot import types
import pandas as pd
import os
import threading
import random
from flask import Flask

# Tokeningiz
TOKEN = '6844735110:AAHybqfU2qnfxXuy7MGUG-VxvMWs3aP_5f8'
bot = telebot.TeleBot(TOKEN)
app = Flask(__name__)

# --- SIZNING TELEGRAM ID RAQAMINGIZ ---
ADMIN_ID = 6761276533
# --------------------------------------

# Yangi baza nomi (xato bermasligi uchun)
DB_FILE = "feniks_baza_v3.csv" 

# 1. Bazani yaratish va yuklash
def load_data():
    if os.path.exists(DB_FILE):
        return pd.read_csv(DB_FILE)
    else:
        # Boshlang'ich ma'lumotlar va parollar
        df = pd.DataFrame({
            "Ism": ["Zoom", "Umarbek", "AMIN", "Bexruz", "Komron", "Shabnam", "Kamilla", "Tarjimon", "Feniks"],
            "Ishladi": [1400000, 300000, 200000, 400000, 400000, 200000, 200000, 100000, 2360000],
            "To'landi": [700000, 200000, 150000, 400000, 400000, 100000, 100000, 0, 2360000],
            "Telegram_ID": [0]*9,
            "Parol": [str(random.randint(1000, 9999)) for _ in range(9)]
        })
        # Siz (Feniks) uchun maxsus sozlama (Sizga parol kerak emas)
        df.loc[df["Ism"] == "Feniks", "Telegram_ID"] = ADMIN_ID
        df.loc[df["Ism"] == "Feniks", "Parol"] = "Admin"
        df.to_csv(DB_FILE, index=False)
        return df

def save_data(df):
    df.to_csv(DB_FILE, index=False)

# 2. Tugmalar menyusi
def admin_menu():
    markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    markup.add("📊 Jami Hisobot", "🔑 Aktyorlarga Parol", "➕ Pul To'lash", "📝 Ish Qo'shish", "👤 Yangi Aktyor")
    return markup

def actor_menu():
    markup = types.ReplyKeyboardMarkup(row_width=1, resize_keyboard=True)
    markup.add("💰 Mening Hisobim")
    return markup

# 3. Start va tizimga kirish
@bot.message_handler(commands=['start'])
def start(message):
    user_id = message.from_user.id
    df = load_data()
    
    # Agar Siz (Admin) kirsangiz
    if user_id == ADMIN_ID:
        bot.send_message(message.chat.id, "🎬 **FeniksStudio Boshqaruv Paneliga xush kelibsiz, Rejissyor!**", reply_markup=admin_menu(), parse_mode="Markdown")
        return
        
    # Agar ro'yxatdan o'tgan aktyor kirsa
    if user_id in df["Telegram_ID"].values:
        actor_name = df.loc[df["Telegram_ID"] == user_id, "Ism"].values[0]
        bot.send_message(message.chat.id, f"Salom, **{actor_name}**!\nFeniksStudio shaxsiy kabinetingizga xush kelibsiz.", reply_markup=actor_menu(), parse_mode="Markdown")
        return
        
    # Notanish odam yoki birinchi marta kirayotgan aktyor
    bot.send_message(message.chat.id, "🔐 **FeniksStudio** yopiq tizimi.\n\nIltimos, rejissyor bergan 4 xonali parolni yuboring:")

# 4. Parol orqali avtorizatsiya (Aktyorlar uchun)
@bot.message_handler(func=lambda msg: msg.text.isdigit() and len(msg.text) == 4)
def login_actor(message):
    df = load_data()
    parol = message.text
    
    if parol in df["Parol"].values:
        actor_name = df.loc[df["Parol"] == parol, "Ism"].values[0]
        # ID ni saqlab, parolni yoqib yuboramiz (Xavfsizlik)
        df.loc[df["Parol"] == parol, "Telegram_ID"] = message.from_user.id
        df.loc[df["Parol"] == parol, "Parol"] = "Ishlatilgan"
        save_data(df)
        bot.send_message(message.chat.id, f"✅ Muvaffaqiyatli kirdingiz, **{actor_name}**!", reply_markup=actor_menu(), parse_mode="Markdown")
    else:
        bot.send_message(message.chat.id, "❌ Noto'g'ri parol. Qaytadan urinib ko'ring yoki rahbariyatga murojaat qiling.")

# ==========================================
# AKTYORLAR UCHUN FUNKSIYALAR
# ==========================================
@bot.message_handler(func=lambda msg: msg.text == "💰 Mening Hisobim")
def my_balance(message):
    df = load_data()
    user_id = message.from_user.id
    if user_id in df["Telegram_ID"].values:
        row = df[df["Telegram_ID"] == user_id].iloc[0]
        qarz = int(row["Ishladi"]) - int(row["To'landi"])
        status = "✅ Sizda qarz yo'q" if qarz <= 0 else f"❌ To'lanishi kerak: {qarz:,} so'm"
        text = f"👤 **Aktyor:** {row['Ism']}\n🎬 **Jami ishlagan:** {int(row['Ishladi']):,} so'm\n💸 **Qo'lga tekkan:** {int(row['To\'landi']):,} so'm\n----------------------\n{status}"
        bot.send_message(message.chat.id, text, parse_mode="Markdown")

# ==========================================
# REJISSYOR (ADMIN) UCHUN FUNKSIYALAR
# ==========================================

# Parollarni ko'rish
@bot.message_handler(func=lambda msg: msg.from_user.id == ADMIN_ID and msg.text == "🔑 Aktyorlarga Parol")
def show_passwords(message):
    df = load_data()
    text = "🔐 **Aktyorlar uchun kirish parollari:**\nShu kodlarni ularga bering:\n\n"
    for _, row in df.iterrows():
        if row["Ism"] != "Feniks":
            status = "✅ Kirdi" if row["Telegram_ID"] != 0 else f"`{row['Parol']}`"
            text += f"👤 {row['Ism']}: {status}\n"
    bot.send_message(message.chat.id, text, parse_mode="Markdown")

# Jami Hisobot
@bot.message_handler(func=lambda msg: msg.from_user.id == ADMIN_ID and msg.text == "📊 Jami Hisobot")
def admin_report(message):
    df = load_data()
    df["Qarz"] = df["Ishladi"] - df["To'landi"]
    msg = "📊 **FENIKS STUDIO HISOBOTI**\n-------------------\n"
    for _, row in df.iterrows():
        status = "✅" if row["Qarz"] <= 0 else "❌"
        msg += f"{status} {row['Ism']}: {row['Qarz']:,} so'm\n"
    total_debt = df.loc[df["Ism"] != "Feniks", "Qarz"].sum()
    msg += f"-------------------\n🔴 **Jami tarqatish kerak:** {total_debt:,} so'm"
    bot.send_message(message.chat.id, msg)

# Pul To'lash
@bot.message_handler(func=lambda msg: msg.from_user.id == ADMIN_ID and msg.text == "➕ Pul To'lash")
def pay_actor_btn(message):
    df = load_data()
    markup = types.InlineKeyboardMarkup(row_width=3)
    buttons = []
    for name in df['Ism']:
        ishladi = int(df.loc[df['Ism']==name, 'Ishladi'].values[0])
        tolandi = int(df.loc[df['Ism']==name, "To'landi"].values[0])
        if ishladi > tolandi:
            buttons.append(types.InlineKeyboardButton(name, callback_data=f"pay_{name}"))
    markup.add(*buttons)
    if not buttons:
        bot.send_message(message.chat.id, "✅ Hamma qarzlar uzilgan! Hech kimdan qarz emassiz.")
    else:
        bot.send_message(message.chat.id, "Kimga pul to'layapsiz? (Qarzi borlar):", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.from_user.id == ADMIN_ID and call.data.startswith("pay_"))
def ask_pay_amount(call):
    actor = call.data.split("_")[1]
    bot.answer_callback_query(call.id)
    msg = bot.send_message(call.message.chat.id, f"💰 **{actor}**ga qancha berdingiz? (Faqat raqam yozing)", parse_mode="Markdown")
    bot.register_next_step_handler(msg, process_payment, actor)

def process_payment(message, actor):
    if message.from_user.id != ADMIN_ID: return
    try:
        amount = int(message.text)
        df = load_data()
        df.loc[df["Ism"] == actor, "To'landi"] += amount
        save_data(df)
        qarz = int(df.loc[df["Ism"] == actor, "Ishladi"].values[0]) - int(df.loc[df["Ism"] == actor, "To'landi"].values[0])
        bot.send_message(message.chat.id, f"✅ Muvaffaqiyatli!\n👤 {actor}ning hisobidan {amount:,} so'm ayirildi.\n📉 Qolgan qarzi: {qarz:,} so'm", parse_mode="Markdown")
    except:
        bot.send_message(message.chat.id, "⚠️ Xato! Boshidan boshlang va faqat raqam yozing.")

# Yangi Ish Qo'shish
@bot.message_handler(func=lambda msg: msg.from_user.id == ADMIN_ID and msg.text == "📝 Ish Qo'shish")
def add_work_btn(message):
    df = load_data()
    markup = types.InlineKeyboardMarkup(row_width=3)
    buttons = [types.InlineKeyboardButton(name, callback_data=f"work_{name}") for name in df['Ism']]
    markup.add(*buttons)
    bot.send_message(message.chat.id, "Kim yangi dublyaj qildi (Ishladi)?", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.from_user.id == ADMIN_ID and call.data.startswith("work_"))
def ask_work_amount(call):
    actor = call.data.split("_")[1]
    bot.answer_callback_query(call.id)
    msg = bot.send_message(call.message.chat.id, f"🎬 **{actor}** qancha ishladi? (So'mda yozing)", parse_mode="Markdown")
    bot.register_next_step_handler(msg, process_work, actor)

def process_work(message, actor):
    if message.from_user.id != ADMIN_ID: return
    try:
        amount = int(message.text)
        df = load_data()
        df.loc[df["Ism"] == actor, "Ishladi"] += amount
        save_data(df)
        bot.send_message(message.chat.id, f"✅ {actor}ning hisobiga {amount:,} so'm qo'shildi!")
    except:
        bot.send_message(message.chat.id, "⚠️ Xato! Boshidan boshlang.")

# Yangi Aktyor Qo'shish
@bot.message_handler(func=lambda msg: msg.from_user.id == ADMIN_ID and msg.text == "👤 Yangi Aktyor")
def add_actor_btn(message):
    msg = bot.send_message(message.chat.id, "Yangi aktyorning ismini yozing:")
    bot.register_next_step_handler(msg, process_add_actor)

def process_add_actor(message):
    if message.from_user.id != ADMIN_ID: return
    new_name = message.text.capitalize()
    df = load_data()
    
    if new_name in df["Ism"].values:
        bot.send_message(message.chat.id, "⚠️ Bu ism bazada bor.")
        return
    
    new_parol = str(random.randint(1000, 9999))
    new_row = pd.DataFrame({"Ism": [new_name], "Ishladi": [0], "To'landi": [0], "Telegram_ID": [0], "Parol": [new_parol]})
    df = pd.concat([df, new_row], ignore_index=True)
    save_data(df)
    
    bot.send_message(message.chat.id, f"✅ **{new_name}** bazaga qo'shildi!\n\n🔑 Uning tizimga kirish paroli: `{new_parol}`", parse_mode="Markdown")

# Render uchun "Aldamchi" sahifa
@app.route('/')
def index(): return "FeniksStudio is running perfectly!"

def run_bot(): bot.polling(none_stop=True)

if __name__ == "__main__":
    threading.Thread(target=run_bot).start()
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
            
