import telebot
from telebot import types
import pandas as pd
import os
import threading
import random
from datetime import datetime
import google.generativeai as genai
from flask import Flask

# ==========================================
# ⚙️ ASOSIY SOZLAMALAR
# ==========================================
TOKEN = '6844735110:AAHybqfU2qnfxXuy7MGUG-VxvMWs3aP_5f8'
GEMINI_KEY = 'AIzaSyDWUfZvr3Tq2O87HyYT9UjX_1O8OJf26Iw'
ADMIN_ID = 6761276533
CHANNEL_ID = -1003634886616 

# AI Integratsiyasi (Xatolik to'g'irlandi)
genai.configure(api_key=GEMINI_KEY)
ai_model = genai.GenerativeModel('gemini-pro') 

bot = telebot.TeleBot(TOKEN, parse_mode="Markdown")
app = Flask(__name__)

DB_FILE = "feniks_v6.csv"
PROJECTS_FILE = "projects_v6.csv"

# ==========================================
# 🗄 MA'LUMOTLAR BAZASI
# ==========================================
def load_data():
    if not os.path.exists(DB_FILE):
        df = pd.DataFrame({
            "Ism": ["Zoom", "Umarbek", "AMIN", "Bexruz", "Komron", "Shabnam", "Kamilla", "Tarjimon", "Feniks"],
            "Ishladi": [1400000, 300000, 200000, 400000, 400000, 200000, 200000, 100000, 2360000],
            "To'landi": [700000, 200000, 150000, 400000, 400000, 100000, 100000, 0, 2360000],
            "Telegram_ID": [0]*9,
            "Parol": [str(random.randint(1000, 9999)) for _ in range(9)]
        })
        df.loc[df["Ism"] == "Feniks", "Telegram_ID"] = ADMIN_ID
        df.loc[df["Ism"] == "Feniks", "Parol"] = "Admin"
        df.to_csv(DB_FILE, index=False)
    return pd.read_csv(DB_FILE)

def load_projects():
    if not os.path.exists(PROJECTS_FILE):
        df = pd.DataFrame({
            "Nomi": ["Gravity Falls", "Sin Mu"],
            "Narx": [50000, 60000], # 1 qism uchun avtomat to'lanadigan narx (so'm)
            "Deadline": ["Belgilanmagan", "Belgilanmagan"]
        })
        df.to_csv(PROJECTS_FILE, index=False)
    return pd.read_csv(PROJECTS_FILE)

def save_data(df, filename):
    df.to_csv(filename, index=False)

# ==========================================
# 🎛 MENYULAR 
# ==========================================
def main_menu(user_id):
    markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    if user_id == ADMIN_ID:
        markup.add("📊 Moliya", "➕ Hisob-Kitob", "🎬 Loyihalar", "🔑 Parollar", "📢 E'lon", "📁 Excel")
    else:
        markup.add("💰 Mening Hisobim", "🎙 Ovoz topshirish", "📖 AI Tarjimon")
    return markup

# ==========================================
# 🚀 START VA AVTORIZATSIYA
# ==========================================
@bot.message_handler(commands=['start'])
def start(message):
    df = load_data()
    user_id = message.from_user.id
    if user_id == ADMIN_ID:
        bot.send_message(message.chat.id, "👑 **FeniksStudio Rejissyor Paneli**\n\nTizim 100% quvvat bilan ishlamoqda.", reply_markup=main_menu(user_id))
    elif user_id in df["Telegram_ID"].values:
        actor = df.loc[df["Telegram_ID"] == user_id, "Ism"].values[0]
        bot.send_message(message.chat.id, f"🎧 Salom, **{actor}**!\nFeniksStudio shaxsiy kabinetingizdasiz.", reply_markup=main_menu(user_id))
    else:
        bot.send_message(message.chat.id, "🔐 **FeniksStudio Maxfiy Tizimi**\n\nIltimos, sizga berilgan 4 xonali PIN-kodni yozing:")

@bot.message_handler(func=lambda m: m.text.isdigit() and len(m.text) == 4)
def login(message):
    df = load_data()
    pin = message.text
    if pin in df["Parol"].values:
        actor = df.loc[df["Parol"] == pin, "Ism"].values[0]
        df.loc[df["Parol"] == pin, "Telegram_ID"] = message.from_user.id
        df.loc[df["Parol"] == pin, "Parol"] = "Yopiq"
        save_data(df, DB_FILE)
        bot.send_message(message.chat.id, f"✅ Muvaffaqiyatli kirdingiz, **{actor}**!", reply_markup=main_menu(message.from_user.id))
    else:
        bot.send_message(message.chat.id, "❌ PIN-kod xato.")

# ==========================================
# 💰 HISOB-KITOB VA MOLIYA (Oldin ishlamagan bo'limlar)
# ==========================================
@bot.message_handler(func=lambda m: m.text == "📊 Moliya" and m.from_user.id == ADMIN_ID)
def admin_report(message):
    df = load_data()
    txt = "📊 **FENIKS STUDIO UMUMIY HISOBOT**\n━━━━━━━━━━━━━━━━━━━━\n"
    jami_qarz = 0
    for _, row in df.iterrows():
        qarz = int(row["Ishladi"]) - int(row["To'landi"])
        if qarz > 0:
            txt += f"🔴 **{row['Ism']}**: {qarz:,} so'm qarzimiz bor\n"
            jami_qarz += qarz
        else:
            txt += f"🟢 **{row['Ism']}**: Hisob-kitob qilingan\n"
    txt += f"━━━━━━━━━━━━━━━━━━━━\n🔴 **Jami berilishi kerak:** {jami_qarz:,} so'm"
    bot.send_message(message.chat.id, txt)

@bot.message_handler(func=lambda m: m.text == "💰 Mening Hisobim")
def my_balance(message):
    df = load_data()
    user_id = message.from_user.id
    if user_id in df["Telegram_ID"].values:
        row = df[df["Telegram_ID"] == user_id].iloc[0]
        qarz = int(row["Ishladi"]) - int(row["To'landi"])
        status = "✅ Sizda qarz yo'q" if qarz <= 0 else f"❌ To'lanishi kerak: {qarz:,} so'm"
        text = f"👤 **Aktyor:** {row['Ism']}\n🎬 **Jami ishlagan:** {int(row['Ishladi']):,} so'm\n💸 **Qo'lga tekkan:** {int(row['To\'landi']):,} so'm\n━━━━━━━━━━━━━━━━━━━━\n{status}"
        bot.send_message(message.chat.id, text)

@bot.message_handler(func=lambda m: m.text == "➕ Hisob-Kitob" and m.from_user.id == ADMIN_ID)
def pay_actor_menu(message):
    df = load_data()
    markup = types.InlineKeyboardMarkup(row_width=3)
    buttons = []
    for _, row in df.iterrows():
        if int(row["Ishladi"]) > int(row["To'landi"]):
            buttons.append(types.InlineKeyboardButton(row["Ism"], callback_data=f"pay_{row['Ism']}"))
    markup.add(*buttons)
    if not buttons:
        bot.send_message(message.chat.id, "✅ Hamma qarzlar uzilgan!")
    else:
        bot.send_message(message.chat.id, "Kimga pul to'layapsiz? (Qarzi borlar):", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("pay_"))
def ask_pay_amount(call):
    actor = call.data.split("_")[1]
    msg = bot.send_message(call.message.chat.id, f"💰 **{actor}**ga qancha berdingiz? (Faqat raqam)")
    bot.register_next_step_handler(msg, process_payment, actor)

def process_payment(message, actor):
    try:
        amount = int(message.text)
        df = load_data()
        df.loc[df["Ism"] == actor, "To'landi"] += amount
        save_data(df, DB_FILE)
        qarz = int(df.loc[df["Ism"] == actor, "Ishladi"].values[0]) - int(df.loc[df["Ism"] == actor, "To'landi"].values[0])
        bot.send_message(message.chat.id, f"✅ Muvaffaqiyatli!\n👤 {actor}ga {amount:,} so'm yozildi.\n📉 Qolgan qarz: {qarz:,} so'm")
    except:
        bot.send_message(message.chat.id, "⚠️ Xato! Faqat raqam kiriting.")

# ==========================================
# 🎙 OVOZ TOPSHIRISH (AVTOMATIK SMETA VA KANAL)
# ==========================================
@bot.message_handler(func=lambda m: m.text == "🎙 Ovoz topshirish")
def voice_guide(message):
    bot.send_message(message.chat.id, "🎬 **Ovoz topshirish bo'yicha qo'llanma:**\n\nShunchaki tayyor ovozingizni (Voice yoki MP3) botga yuboring. Bot sizdan qaysi loyiha ekanligini so'raydi va avtomatik ravishda hisobingizga pul yozib, kanalga joylaydi.")

user_audio_cache = {}

@bot.message_handler(content_types=['voice', 'audio'])
def receive_audio(message):
    df = load_data()
    user_id = message.from_user.id
    if user_id not in df["Telegram_ID"].values: return
    
    actor = df.loc[df["Telegram_ID"] == user_id, "Ism"].values[0]
    user_audio_cache[user_id] = {'msg': message, 'actor': actor}
    
    pr_df = load_projects()
    markup = types.InlineKeyboardMarkup(row_width=2)
    buttons = [types.InlineKeyboardButton(p, callback_data=f"pr_{p}") for p in pr_df["Nomi"]]
    markup.add(*buttons)
    
    bot.send_message(message.chat.id, f"🔥 Ovoz qabul qilindi!\n\n**Bu qaysi loyiha uchun?** (Tugmani bosing)", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("pr_"))
def ask_part(call):
    project = call.data.split("_")[1]
    user_id = call.from_user.id
    bot.delete_message(call.message.chat.id, call.message.message_id)
    
    user_audio_cache[user_id]['project'] = project
    msg = bot.send_message(call.message.chat.id, f"🔢 **{project}** loyihasining nechinchi qismi? (Raqam yozing):")
    bot.register_next_step_handler(msg, send_to_channel, user_id)

def send_to_channel(message, user_id):
    part = message.text
    data = user_audio_cache.get(user_id)
    if not data: return
    
    # Avtomatik Smeta (Pul qo'shish)
    pr_df = load_projects()
    price = int(pr_df.loc[pr_df["Nomi"] == data['project'], "Narx"].values[0])
    
    df = load_data()
    df.loc[df["Ism"] == data['actor'], "Ishladi"] += price
    save_data(df, DB_FILE)
    
    caption = (
        f"🎙 **YANGI DUBLYAZH KELDI**\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"🎬 **Loyiha:** {data['project']}\n"
        f"👤 **Aktyor:** {data['actor']}\n"
        f"🔢 **Qism:** {part}\n"
        f"💰 **Smeta:** {price:,} so'm yozildi\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"⚙️ Holat: _O'tkazish (Tayyor)_\n"
        f"#{data['project'].replace(' ', '')}"
    )
    
    try:
        if data['msg'].content_type == 'voice':
            bot.send_voice(CHANNEL_ID, data['msg'].voice.file_id, caption=caption)
        else:
            bot.send_audio(CHANNEL_ID, data['msg'].audio.file_id, caption=caption)
        bot.send_message(message.chat.id, f"✅ **Kanalga joylandi!**\nSizning hisobingizga **{price:,} so'm** qo'shildi.")
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Kanalga yuborishda xatolik. Kanal ID to'g'riligini tekshiring.")
    
    del user_audio_cache[user_id]

# ==========================================
# 🤖 AI TARJIMON (Gemini-Pro)
# ==========================================
@bot.message_handler(func=lambda m: m.text == "📖 AI Tarjimon")
def ai_guide(message):
    bot.send_message(message.chat.id, "🤖 **AI Tarjimon ishga tayyor!**\n\nMenga so'z yoki matnni yuboring, oldiga `Tarjima:` deb yozing.\nMisol: `Tarjima: Stay strong`")

@bot.message_handler(func=lambda m: m.text.startswith("Tarjima:"))
def translate_ai(message):
    text = message.text.replace("Tarjima:", "").strip()
    wait_msg = bot.reply_to(message, "⏳ _Gemini AI o'ylamoqda..._")
    try:
        prompt = f"Sen dublyaj aktyorlari uchun yordamchisan. Quyidagi matnni o'zbekchaga tarjima qil va qanday hissiyot bilan aytishni qisqacha yoz:\n\n'{text}'"
        response = ai_model.generate_content(prompt)
        bot.edit_message_text(f"🤖 **Feniks AI:**\n\n{response.text}", chat_id=message.chat.id, message_id=wait_msg.message_id)
    except Exception as e:
        bot.edit_message_text(f"⚠️ AI tarmog'ida xatolik: {e}", chat_id=message.chat.id, message_id=wait_msg.message_id)

# ==========================================
# BOSHQA ADMIN FUNKSIYALARI (Parollar, Excel, Loyihalar)
# ==========================================
@bot.message_handler(func=lambda m: m.text == "🔑 Parollar" and m.from_user.id == ADMIN_ID)
def show_pins(message):
    df = load_data()
    txt = "🔐 **Aktyorlar PIN-kodlari:**\n\n"
    for _, row in df.iterrows():
        if row['Ism'] != 'Feniks':
            status = "✅ Kirdi" if row['Telegram_ID'] != 0 else f"`{row['Parol']}`"
            txt += f"👤 {row['Ism']}: {status}\n"
    bot.send_message(message.chat.id, txt)

@bot.message_handler(func=lambda m: m.text == "📁 Excel" and m.from_user.id == ADMIN_ID)
def export_excel(message):
    load_data().to_excel("Feniks_Moliya.xlsx", index=False)
    with open("Feniks_Moliya.xlsx", "rb") as f:
        bot.send_document(message.chat.id, f, caption="📊 FeniksStudio Buxgalteriya")

@bot.message_handler(func=lambda m: m.text == "🎬 Loyihalar" and m.from_user.id == ADMIN_ID)
def projects_menu(message):
    df = load_projects()
    txt = "📁 **Faol Loyihalar:**\n\n"
    for _, row in df.iterrows():
        txt += f"🔸 **{row['Nomi']}** (1 qism narxi: {row['Narx']:,} so'm)\n"
    bot.send_message(message.chat.id, txt)

# Server uyg'oq turishi uchun
@app.route('/')
def keep_alive(): return "FeniksStudio Elite v6.0 is 100% Online!"

if __name__ == "__main__":
    threading.Thread(target=lambda: bot.polling(none_stop=True)).start()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
    
