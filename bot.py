import telebot
from telebot import types
import pandas as pd
import os
import threading
import random
from flask import Flask

# --- SOZLAMALAR ---
TOKEN = '6844735110:AAHybqfU2qnfxXuy7MGUG-VxvMWs3aP_5f8'
ADMIN_ID = 6761276533
CHANNEL_ID = -1003634886616 

bot = telebot.TeleBot(TOKEN, parse_mode="Markdown")
app = Flask(__name__)

DB_FILE = "feniks_v7.csv"
PROJECTS_FILE = "projects_v7.csv"

# --- MA'LUMOTLARNI YUKLASH ---
def load_data():
    if not os.path.exists(DB_FILE):
        # Boshlang'ich aktyorlar
        actors = ["Zoom", "Umarbek", "AMIN", "Bexruz", "Komron", "Shabnam", "Kamilla", "Tarjimon", "Feniks"]
        df = pd.DataFrame({
            "Ism": actors,
            "Ishladi": [0]*9,
            "To'landi": [0]*9,
            "Telegram_ID": [0]*9,
            "Parol": [str(random.randint(1000, 9999)) for _ in range(9)]
        })
        df.loc[df["Ism"] == "Feniks", "Telegram_ID"] = ADMIN_ID
        df.to_csv(DB_FILE, index=False)
    return pd.read_csv(DB_FILE)

def load_projects():
    if not os.path.exists(PROJECTS_FILE):
        # Loyiha nomi, Aktyor ismi, Stavka (narx)
        df = pd.DataFrame(columns=["Loyiha", "Aktyor", "Narx"])
        df.to_csv(PROJECTS_FILE, index=False)
    return pd.read_csv(PROJECTS_FILE)

def save_df(df, file):
    df.to_csv(file, index=False)

# --- MENYULAR ---
def main_menu(user_id):
    markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    if user_id == ADMIN_ID:
        markup.add("📊 Moliya", "➕ Hisob-Kitob", "🎬 Loyihalar", "🔑 Parollar", "📁 Excel")
    else:
        markup.add("💰 Mening Hisobim", "🎙 Ovoz topshirish")
    return markup

# --- START ---
@bot.message_handler(commands=['start'])
def start(message):
    df = load_data()
    user_id = message.from_user.id
    if user_id == ADMIN_ID:
        bot.send_message(message.chat.id, "👑 **FeniksStudio Boshqaruv Markazi**", reply_markup=main_menu(user_id))
    elif user_id in df["Telegram_ID"].values:
        bot.send_message(message.chat.id, "🎧 Salom! Dublyaj xonasiga xush kelibsiz.", reply_markup=main_menu(user_id))
    else:
        bot.send_message(message.chat.id, "🔐 Iltimos, PIN-kodni kiriting:")

@bot.message_handler(func=lambda m: m.text.isdigit() and len(m.text) == 4)
def login(message):
    df = load_data()
    if message.text in df["Parol"].values:
        actor = df.loc[df["Parol"] == message.text, "Ism"].values[0]
        df.loc[df["Parol"] == message.text, "Telegram_ID"] = message.from_user.id
        save_df(df, DB_FILE)
        bot.send_message(message.chat.id, f"✅ Xush kelibsiz, {actor}!", reply_markup=main_menu(message.from_user.id))
    else:
        bot.send_message(message.chat.id, "❌ PIN xato.")

# --- LOYIHALARNI BOSHQARISH (ADMIN) ---
@bot.message_handler(func=lambda m: m.text == "🎬 Loyihalar" and m.from_user.id == ADMIN_ID)
def manage_projects(message):
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(types.InlineKeyboardButton("➕ Yangi Loyiha", callback_data="add_p"))
    markup.add(types.InlineKeyboardButton("❌ Loyihani O'chirish", callback_data="del_p"))
    
    pr_df = load_projects()
    if pr_df.empty:
        bot.send_message(message.chat.id, "Hozircha loyihalar yo'q.", reply_markup=markup)
    else:
        txt = "📁 **Mavjud Loyihalar:**\n"
        # Faqat noyob loyiha nomlarini ko'rsatish
        for p in pr_df["Loyiha"].unique():
            txt += f"🔸 {p}\n"
        bot.send_message(message.chat.id, txt, reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data == "add_p")
def add_p_start(call):
    msg = bot.send_message(call.message.chat.id, "Loyiha nomini yozing (masalan: Sin Mu):")
    bot.register_next_step_handler(msg, add_p_step2)

def add_p_step2(message):
    p_name = message.text
    df_actors = load_data()
    markup = types.InlineKeyboardMarkup(row_width=2)
    for a in df_actors["Ism"]:
        if a != "Feniks":
            markup.add(types.InlineKeyboardButton(a, callback_data=f"setrate_{p_name}_{a}"))
    markup.add(types.InlineKeyboardButton("✅ TUGATISH", callback_data="main_menu_back"))
    bot.send_message(message.chat.id, f"'{p_name}' uchun aktyorlarni tanlab, narxini belgilang:", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("setrate_"))
def set_rate_step1(call):
    _, p_name, actor = call.data.split("_")
    msg = bot.send_message(call.message.chat.id, f"💰 **{actor}** uchun '{p_name}' loyihasida 1 qism narxi qancha? (Raqam yozing)")
    bot.register_next_step_handler(msg, set_rate_step2, p_name, actor)

def set_rate_step2(message, p_name, actor):
    try:
        rate = int(message.text)
        pr_df = load_projects()
        # Eski bo'lsa o'chirish, yangisini qo'shish (Update)
        pr_df = pr_df[~((pr_df["Loyiha"] == p_name) & (pr_df["Aktyor"] == actor))]
        new_row = pd.DataFrame({"Loyiha": [p_name], "Aktyor": [actor], "Narx": [rate]})
        pr_df = pd.concat([pr_df, new_row], ignore_index=True)
        save_df(pr_df, PROJECTS_FILE)
        bot.send_message(message.chat.id, f"✅ Saqlandi: {actor} - {rate:,} so'm")
    except:
        bot.send_message(message.chat.id, "⚠️ Faqat raqam kiriting!")

# --- OVOZ TOPSHIRISH ---
user_audio_cache = {}

@bot.message_handler(content_types=['voice', 'audio'])
def handle_audio(message):
    df = load_data()
    if message.from_user.id not in df["Telegram_ID"].values: return
    
    actor = df.loc[df["Telegram_ID"] == message.from_user.id, "Ism"].values[0]
    user_audio_cache[message.from_user.id] = {'msg': message, 'actor': actor}
    
    pr_df = load_projects()
    # Faqat shu aktyor qatnashayotgan loyihalarni ko'rsatish
    my_projects = pr_df[pr_df["Aktyor"] == actor]["Loyiha"].unique()
    
    markup = types.InlineKeyboardMarkup(row_width=2)
    for p in my_projects:
        markup.add(types.InlineKeyboardButton(p, callback_data=f"dub_{p}"))
    
    if not my_projects.any():
        bot.send_message(message.chat.id, "❌ Siz hali birorta loyihaga qo'shilmagansiz.")
    else:
        bot.send_message(message.chat.id, "Qaysi loyiha uchun ovoz berdingiz?", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("dub_"))
def dub_step2(call):
    project = call.data.split("_")[1]
    user_id = call.from_user.id
    user_audio_cache[user_id]['project'] = project
    msg = bot.send_message(call.message.chat.id, f"'{project}' ning nechinchi qismi? (Raqam yozing)")
    bot.register_next_step_handler(msg, final_process)

def final_process(message):
    user_id = message.from_user.id
    try:
        part = message.text
        data = user_audio_cache[user_id]
        
        pr_df = load_projects()
        rate = int(pr_df[(pr_df["Loyiha"] == data['project']) & (pr_df["Aktyor"] == data['actor'])]["Narx"].values[0])
        
        # Balansni yangilash
        df = load_data()
        df.loc[df["Ism"] == data['actor'], "Ishladi"] += rate
        save_df(df, DB_FILE)
        
        # Kanalga yuborish
        caption = f"🎙 **FENIKS STUDIO**\n🎬 **Loyiha:** {data['project']}\n👤 **Aktyor:** {data['actor']}\n🔢 **Qism:** {part}\n💰 **Stavka:** {rate:,} so'm"
        if data['msg'].content_type == 'voice':
            bot.send_voice(CHANNEL_ID, data['msg'].voice.file_id, caption=caption)
        else:
            bot.send_audio(CHANNEL_ID, data['msg'].audio.file_id, caption=caption)
            
        bot.send_message(message.chat.id, f"✅ Hisobingizga {rate:,} so'm qo'shildi va kanalga yuborildi.")
    except:
        bot.send_message(message.chat.id, "⚠️ Xatolik yuz berdi. Qismni to'g'ri yozganingizni tekshiring.")

# --- BOSHQA FUNKSIYALAR (Moliya, Hisobim, Excel) ---
@bot.message_handler(func=lambda m: m.text == "📊 Moliya" and m.from_user.id == ADMIN_ID)
def finance_report(message):
    df = load_data()
    txt = "📊 **FENIKS STUDIO HISOBOTI**\n"
    for _, row in df.iterrows():
        qarz = int(row["Ishladi"]) - int(row["To'landi"])
        txt += f"👤 {row['Ism']}: {qarz:,} so'm\n"
    bot.send_message(message.chat.id, txt)

@bot.message_handler(func=lambda m: m.text == "💰 Mening Hisobim")
def my_account(message):
    df = load_data()
    row = df[df["Telegram_ID"] == message.from_user.id].iloc[0]
    qarz = int(row["Ishladi"]) - int(row["To'landi"])
    bot.send_message(message.chat.id, f"👤 {row['Ism']}\n🎬 Ishlagan: {int(row['Ishladi']):,}\n💸 Olgan: {int(row['To\'landi']):,}\n🔴 Qarz: {qarz:,}")

@bot.callback_query_handler(func=lambda call: call.data == "main_menu_back")
def back_home(call):
    bot.send_message(call.message.chat.id, "Asosiy menyu", reply_markup=main_menu(call.from_user.id))

@app.route('/')
def home(): return "FeniksStudio v7.0 Online!"

if __name__ == "__main__":
    threading.Thread(target=lambda: bot.polling(none_stop=True)).start()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
    
