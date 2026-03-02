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
CHANNEL_ID = -1003634886616 # Sizning rasmiy kanalingiz

# AI Integratsiyasi (Pro rejim)
genai.configure(api_key=GEMINI_KEY)
# Eng so'nggi va tezkor model
ai_model = genai.GenerativeModel('gemini-1.5-flash') 

bot = telebot.TeleBot(TOKEN, parse_mode="Markdown")
app = Flask(__name__)

DB_FILE = "feniks_actors.csv"
PROJECTS_FILE = "feniks_projects.csv"

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
            "Nomi": ["Gravity Falls", "The Looney Tunes Show", "Sin Mu"],
            "Deadline": ["Belgilanmagan", "Belgilanmagan", "Belgilanmagan"]
        })
        df.to_csv(PROJECTS_FILE, index=False)
    return pd.read_csv(PROJECTS_FILE)

def save_data(df, filename):
    df.to_csv(filename, index=False)

# ==========================================
# 🎛 MENYULAR (Zamonaviy UI)
# ==========================================
def main_menu(user_id):
    markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    if user_id == ADMIN_ID:
        markup.add("📊 Moliya", "🎬 Loyihalar", "🔑 Parollar", "➕ Hisob-kitob", "📢 E'lon", "📁 Excel")
    else:
        markup.add("💰 Hisobim", "📖 AI Tarjimon")
        markup.add("🎙 Ovoz topshirish bo'yicha qo'llanma")
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
# 🎙 AVTOMATIK KANALGA YUKLASH (TUGMALAR BILAN)
# ==========================================
user_audio_cache = {} # Vaqtinchalik xotira

@bot.message_handler(content_types=['voice', 'audio'])
def receive_audio(message):
    df = load_data()
    user_id = message.from_user.id
    if user_id not in df["Telegram_ID"].values: return
    
    # Audioni xotiraga saqlaymiz
    user_audio_cache[user_id] = {'msg': message, 'actor': df.loc[df["Telegram_ID"] == user_id, "Ism"].values[0]}
    
    # Loyihalarni tugma qilib chiqaramiz
    pr_df = load_projects()
    markup = types.InlineKeyboardMarkup(row_width=2)
    buttons = [types.InlineKeyboardButton(p, callback_data=f"pr_{p}") for p in pr_df["Nomi"]]
    markup.add(*buttons)
    markup.add(types.InlineKeyboardButton("➕ Boshqa loyiha", callback_data="pr_Boshqa"))
    
    bot.send_message(message.chat.id, "🔥 Qoyilmaqom ijro!\n\n**Bu qaysi loyiha uchun?**", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("pr_"))
def ask_part(call):
    project = call.data.split("_")[1]
    user_id = call.from_user.id
    bot.delete_message(call.message.chat.id, call.message.message_id)
    
    if project == "Boshqa":
        msg = bot.send_message(call.message.chat.id, "Loyiha nomini yozib yuboring:")
        bot.register_next_step_handler(msg, custom_project, user_id)
    else:
        user_audio_cache[user_id]['project'] = project
        msg = bot.send_message(call.message.chat.id, "🔢 **Nechinchi qism?** (Raqam yozing yoki 'Film' deng):")
        bot.register_next_step_handler(msg, send_to_channel, user_id)

def custom_project(message, user_id):
    user_audio_cache[user_id]['project'] = message.text
    msg = bot.send_message(message.chat.id, "🔢 **Nechinchi qism?** (Raqam yozing yoki 'Film' deng):")
    bot.register_next_step_handler(msg, send_to_channel, user_id)

def send_to_channel(message, user_id):
    part = message.text
    data = user_audio_cache.get(user_id)
    if not data: return
    
    # Hash tag yasash (qidirish oson bo'lishi uchun)
    hashtag = "#" + data['project'].replace(" ", "")
    
    caption = (
        f"🎙 **YANGI DUBLYAZH KELDI**\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"🎬 **Loyiha:** {data['project']}\n"
        f"👤 **Aktyor:** {data['actor']}\n"
        f"🔢 **Qism:** {part}\n"
        f"⏱ **Vaqt:** {datetime.now().strftime('%d.%m.%Y | %H:%M')}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"⚙️ Holat: _O'tkazish (Tayyor)_\n"
        f"{hashtag}"
    )
    
    try:
        if data['msg'].content_type == 'voice':
            bot.send_voice(CHANNEL_ID, data['msg'].voice.file_id, caption=caption)
        else:
            bot.send_audio(CHANNEL_ID, data['msg'].audio.file_id, caption=caption)
        bot.send_message(message.chat.id, "✅ **Muvaffaqiyatli!** Ovoz yozuvi to'g'ridan-to'g'ri kanalga joylandi.")
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Kanalga yuborishda xatolik. Bot kanalga admin emasmi?\n{e}")
    
    del user_audio_cache[user_id] # Xotirani tozalash

# ==========================================
# 🤖 AI TARJIMON (Gemini Pro)
# ==========================================
@bot.message_handler(func=lambda m: m.text == "📖 AI Tarjimon")
def ai_guide(message):
    bot.send_message(message.chat.id, "🤖 **AI Tarjimon ishga tayyor!**\n\nMenga so'z yoki matnni yuboring, oldiga `Tarjima:` deb yozing.\nMisol: `Tarjima: Stay strong`")

@bot.message_handler(func=lambda m: m.text.startswith("Tarjima:"))
def translate_ai(message):
    text = message.text.replace("Tarjima:", "").strip()
    wait_msg = bot.reply_to(message, "⏳ _Gemini AI o'ylamoqda..._")
    try:
        prompt = f"Sen FeniksStudio dublyaj jamoasining yordamchisisan. Quyidagi matnni o'zbekchaga tarjima qil va dublyaj aktyori uni qanday hissiyot bilan aytishi kerakligini qisqacha tushuntir:\n\n'{text}'"
        response = ai_model.generate_content(prompt)
        bot.edit_message_text(f"🤖 **Feniks AI Javobi:**\n\n{response.text}", chat_id=message.chat.id, message_id=wait_msg.message_id)
    except Exception as e:
        bot.edit_message_text(f"⚠️ AI tarmog'ida xatolik: {e}", chat_id=message.chat.id, message_id=wait_msg.message_id)

# ==========================================
# 📊 REJISSYOR (ADMIN) BO'LIMI
# ==========================================
@bot.message_handler(func=lambda m: m.text == "📁 Excel" and m.from_user.id == ADMIN_ID)
def export_excel(message):
    load_data().to_excel("Feniks_Moliya.xlsx", index=False)
    with open("Feniks_Moliya.xlsx", "rb") as f:
        bot.send_document(message.chat.id, f, caption="📊 FeniksStudio Buxgalteriya (Excel)")

@bot.message_handler(func=lambda m: m.text == "🔑 Parollar" and m.from_user.id == ADMIN_ID)
def show_pins(message):
    df = load_data()
    txt = "🔐 **Aktyorlar PIN-kodlari:**\n\n"
    for _, row in df.iterrows():
        if row['Ism'] != 'Feniks':
            status = "✅ Kirdi" if row['Telegram_ID'] != 0 else f"`{row['Parol']}`"
            txt += f"👤 {row['Ism']}: {status}\n"
    bot.send_message(message.chat.id, txt)

@bot.message_handler(func=lambda m: m.text == "📢 E'lon" and m.from_user.id == ADMIN_ID)
def ask_broadcast(message):
    msg = bot.send_message(message.chat.id, "Barcha aktyorlarga qanday e'lon bermoqchisiz yozing:")
    bot.register_next_step_handler(msg, send_broadcast)

def send_broadcast(message):
    df = load_data()
    text = f"🚨 **REJISSYORDAN E'LON:**\n\n{message.text}"
    count = 0
    for uid in df["Telegram_ID"]:
        if uid != 0 and uid != ADMIN_ID:
            try:
                bot.send_message(uid, text)
                count += 1
            except: pass
    bot.send_message(message.chat.id, f"✅ Xabar {count} ta aktyorga muvaffaqiyatli yetkazildi.")

@bot.message_handler(func=lambda m: m.text == "🎬 Loyihalar" and m.from_user.id == ADMIN_ID)
def projects_menu(message):
    df = load_projects()
    txt = "📁 **Faol Loyihalar:**\n\n"
    for _, row in df.iterrows():
        txt += f"🔸 **{row['Nomi']}** (Deadline: {row['Deadline']})\n"
    
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("➕ Yangi Loyiha Qo'shish", callback_data="add_proj"))
    bot.send_message(message.chat.id, txt, reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data == "add_proj")
def add_proj_start(call):
    bot.delete_message(call.message.chat.id, call.message.message_id)
    msg = bot.send_message(call.message.chat.id, "Yangi loyiha nomini yozing:")
    bot.register_next_step_handler(msg, save_proj_name)

def save_proj_name(message):
    p_name = message.text
    msg = bot.send_message(message.chat.id, f"'{p_name}' qachon topshirilishi kerak? (Masalan: Ertaga, 25-mart):")
    bot.register_next_step_handler(msg, save_proj_deadline, p_name)

def save_proj_deadline(message, p_name):
    df = load_projects()
    new_row = pd.DataFrame({"Nomi": [p_name], "Deadline": [message.text]})
    save_data(pd.concat([df, new_row]), PROJECTS_FILE)
    bot.send_message(message.chat.id, "✅ Loyiha bazaga qo'shildi!")

# Render "Uxlab qolmasligi" uchun web server
@app.route('/')
def keep_alive(): return "FeniksStudio Elite v5.0 is Online!"

if __name__ == "__main__":
    threading.Thread(target=lambda: bot.polling(none_stop=True)).start()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
        
