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
        df = pd.DataFrame(columns=["Loyiha", "Aktyor", "Narx"])
        df.to_csv(PROJECTS_FILE, index=False)
    return pd.read_csv(PROJECTS_FILE)

def save_df(df, file):
    df.to_csv(file, index=False)

# --- MENYULAR ---
def main_menu(user_id):
    markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    if user_id == ADMIN_ID:
        markup.add("📊 Moliya", "➕ Hisob-Kitob")
        markup.add("🎬 Loyihalar", "🔑 Parollar")
        markup.add("📁 Excel", "👤 Aktyor Qo'shish")
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
        bot.send_message(message.chat.id, "🎧 Salom! Feniks jamoasiga xush kelibsiz.", reply_markup=main_menu(user_id))
    else:
        bot.send_message(message.chat.id, "🔐 Iltimos, kirish PIN-kodini kiriting:")

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

# --- 1. AKTYOR QO'SHISH (ADMIN) ---
@bot.message_handler(func=lambda m: m.text == "👤 Aktyor Qo'shish" and m.from_user.id == ADMIN_ID)
def add_actor_init(message):
    msg = bot.send_message(message.chat.id, "Yangi aktyor ismini kiriting:")
    bot.register_next_step_handler(msg, add_actor_save)

def add_actor_save(message):
    name = message.text
    df = load_data()
    pin = str(random.randint(1000, 9999))
    new_row = pd.DataFrame({"Ism": [name], "Ishladi": [0], "To'landi": [0], "Telegram_ID": [0], "Parol": [pin]})
    df = pd.concat([df, new_row], ignore_index=True)
    save_df(df, DB_FILE)
    bot.send_message(message.chat.id, f"✅ Aktyor qo'shildi!\n👤 Ism: {name}\n🔐 PIN: `{pin}`", reply_markup=main_menu(ADMIN_ID))

# --- 2. HISOB-KITOB (ADMIN) ---
@bot.message_handler(func=lambda m: m.text == "➕ Hisob-Kitob" and m.from_user.id == ADMIN_ID)
def pay_init(message):
    df = load_data()
    markup = types.InlineKeyboardMarkup(row_width=2)
    for _, row in df.iterrows():
        if row["Ism"] != "Feniks":
            markup.add(types.InlineKeyboardButton(row["Ism"], callback_data=f"payto_{row['Ism']}"))
    bot.send_message(message.chat.id, "Kimga pul to'layapsiz?", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("payto_"))
def pay_amount(call):
    actor = call.data.split("_")[1]
    msg = bot.send_message(call.message.chat.id, f"💰 **{actor}** uchun to'lov summasini kiriting:")
    bot.register_next_step_handler(msg, pay_finalize, actor)

def pay_finalize(message, actor):
    try:
        summa = int(message.text)
        df = load_data()
        df.loc[df["Ism"] == actor, "To'landi"] += summa
        save_df(df, DB_FILE)
        
        # Admin tasdiqi
        bot.send_message(ADMIN_ID, f"✅ To'lov tasdiqlandi!\n👤 {actor}: {summa:,} so'm.")
        
        # Aktyorga xabar yuborish
        actor_id = df.loc[df["Ism"] == actor, "Telegram_ID"].values[0]
        if actor_id != 0:
            try:
                bot.send_message(actor_id, f"💸 **To'lov kelib tushdi!**\nSizning hisobingizga {summa:,} so'm qo'shildi. Baraka toping!")
            except:
                pass
    except:
        bot.send_message(ADMIN_ID, "⚠️ Xato! Faqat raqam kiriting.")

# --- 3. PAROLLAR (ADMIN) ---
@bot.message_handler(func=lambda m: m.text == "🔑 Parollar" and m.from_user.id == ADMIN_ID)
def view_passwords(message):
    df = load_data()
    txt = "🔑 **Aktyorlar PIN-kodlari:**\n\n"
    for _, row in df.iterrows():
        status = "✅ Faol" if row["Telegram_ID"] != 0 else "❌ Kirilmagan"
        txt += f"👤 {row['Ism']}: `{row['Parol']}` ({status})\n"
    bot.send_message(message.chat.id, txt)

# --- 4. EXCEL EKSPORT (ADMIN) ---
@bot.message_handler(func=lambda m: m.text == "📁 Excel" and m.from_user.id == ADMIN_ID)
def export_excel(message):
    df = load_data()
    file_name = "FeniksStudio_Hisobot.xlsx"
    df.to_excel(file_name, index=False)
    with open(file_name, "rb") as file:
        bot.send_document(message.chat.id, file, caption="📊 FeniksStudio to'liq moliyaviy jadvali.")

# --- MOLIYA (ADMIN) ---
@bot.message_handler(func=lambda m: m.text == "📊 Moliya" and m.from_user.id == ADMIN_ID)
def finance_report(message):
    df = load_data()
    txt = "📊 **FENIKS STUDIO HISOBOTI**\n\n"
    for _, row in df.iterrows():
        qarz = int(row["Ishladi"]) - int(row["To'landi"])
        txt += f"👤 {row['Ism']}: {qarz:,} so'm\n"
    bot.send_message(message.chat.id, txt)

# --- LOYIHALAR --- (Oldingi ishlayotgan kodingiz saqlandi)
@bot.message_handler(func=lambda m: m.text == "🎬 Loyihalar" and m.from_user.id == ADMIN_ID)
def manage_projects(message):
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(types.InlineKeyboardButton("➕ Yangi Loyiha", callback_data="add_p"))
    pr_df = load_projects()
    if pr_df.empty:
        bot.send_message(message.chat.id, "Hozircha loyihalar yo'q.", reply_markup=markup)
    else:
        txt = "📁 **Mavjud Loyihalar:**\n"
        for p in pr_df["Loyiha"].unique():
            txt += f"🔸 {p}\n"
        bot.send_message(message.chat.id, txt, reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data == "add_p")
def add_p_start(call):
    msg = bot.send_message(call.message.chat.id, "Loyiha nomini yozing:")
    bot.register_next_step_handler(msg, add_p_step2)

def add_p_step2(message):
    p_name = message.text
    df_actors = load_data()
    markup = types.InlineKeyboardMarkup(row_width=2)
    for a in df_actors["Ism"]:
        if a != "Feniks":
            markup.add(types.InlineKeyboardButton(a, callback_data=f"setrate_{p_name}_{a}"))
    markup.add(types.InlineKeyboardButton("✅ TUGATISH", callback_data="main_menu_back"))
    bot.send_message(message.chat.id, f"'{p_name}' uchun aktyorlarga narx belgilang:", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("setrate_"))
def set_rate_step1(call):
    _, p_name, actor = call.data.split("_")
    msg = bot.send_message(call.message.chat.id, f"💰 **{actor}** uchun '{p_name}' 1 qism narxi:")
    bot.register_next_step_handler(msg, set_rate_step2, p_name, actor)

def set_rate_step2(message, p_name, actor):
    try:
        rate = int(message.text)
        pr_df = load_projects()
        pr_df = pr_df[~((pr_df["Loyiha"] == p_name) & (pr_df["Aktyor"] == actor))]
        new_row = pd.DataFrame({"Loyiha": [p_name], "Aktyor": [actor], "Narx": [rate]})
        pr_df = pd.concat([pr_df, new_row], ignore_index=True)
        save_df(pr_df, PROJECTS_FILE)
        bot.send_message(message.chat.id, f"✅ Saqlandi: {actor} - {rate:,} so'm")
    except:
        bot.send_message(message.chat.id, "⚠️ Faqat raqam!")

# --- OVOZ TOPSHIRISH ---
user_audio_cache = {}

@bot.message_handler(content_types=['voice', 'audio'])
def handle_audio(message):
    df = load_data()
    if message.from_user.id not in df["Telegram_ID"].values: return
    actor = df.loc[df["Telegram_ID"] == message.from_user.id, "Ism"].values[0]
    user_audio_cache[message.from_user.id] = {'msg': message, 'actor': actor}
    pr_df = load_projects()
    my_projects = pr_df[pr_df["Aktyor"] == actor]["Loyiha"].unique()
    markup = types.InlineKeyboardMarkup(row_width=2)
    for p in my_projects:
        markup.add(types.InlineKeyboardButton(p, callback_data=f"dub_{p}"))
    if not my_projects.any():
        bot.send_message(message.chat.id, "❌ Siz loyihaga qo'shilmagansiz.")
    else:
        bot.send_message(message.chat.id, "Loyiha tanlang:", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("dub_"))
def dub_step2(call):
    project = call.data.split("_")[1]
    user_audio_cache[call.from_user.id]['project'] = project
    msg = bot.send_message(call.message.chat.id, "Nechinchi qism?")
    bot.register_next_step_handler(msg, final_process)

def final_process(message):
    try:
        user_id = message.from_user.id
        data = user_audio_cache[user_id]
        pr_df = load_projects()
        rate = int(pr_df[(pr_df["Loyiha"] == data['project']) & (pr_df["Aktyor"] == data['actor'])]["Narx"].values[0])
        df = load_data()
        df.loc[df["Ism"] == data['actor'], "Ishladi"] += rate
        save_df(df, DB_FILE)
        caption = f"🎙 **FENIKS STUDIO**\n🎬 **Loyiha:** {data['project']}\n👤 **Aktyor:** {data['actor']}\n🔢 **Qism:** {message.text}\n💰 **Stavka:** {rate:,} so'm"
        if data['msg'].content_type == 'voice':
            bot.send_voice(CHANNEL_ID, data['msg'].voice.file_id, caption=caption)
        else:
            bot.send_audio(CHANNEL_ID, data['msg'].audio.file_id, caption=caption)
        bot.send_message(message.chat.id, f"✅ Hisobingizga {rate:,} so'm qo'shildi.")
    except:
        bot.send_message(message.chat.id, "⚠️ Xatolik yuz berdi.")

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
def home(): return "Feniks v7.5 Online!"

if __name__ == "__main__":
    threading.Thread(target=lambda: bot.polling(none_stop=True)).start()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
                                                  
