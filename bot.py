import telebot
from telebot import types
import pandas as pd
import os
import threading
import random
from flask import Flask

# ==========================================
# ⚙️ ASOSIY SOZLAMALAR
# ==========================================
TOKEN = '6844735110:AAE1y58TDn1Kah9SewVx_IFTHBXNZOupJ4w'
ADMIN_ID = 6761276533
CHANNEL_ID = -1003634886616 

bot = telebot.TeleBot(TOKEN, parse_mode="Markdown")
app = Flask(__name__)

DB_FILE = "feniks_v11.csv"
PROJECTS_FILE = "projects_v11.csv"
MENU_FILE = "custom_menu_v11.csv"
TASKS_FILE = "tasks_v11.csv"
TEXTS_FILE = "texts_v11.csv" 

STATIC_BUTTONS = ["📊 Moliya", "➕ Hisob-Kitob", "🎬 Loyihalar", "👤 Aktyor Qo'shish", "🔑 Parollar", "📁 Excel", "📝 Vazifa Qo'shish", "🛠 Menu Builder", "🔤 Tizim Matnlari", "🎙 Ovoz topshirish", "💰 Mening Hisobim", "📋 Faol Vazifalar"]

# ==========================================
# 🗄 BAZANI YUKLASH
# ==========================================
def load_data():
    if not os.path.exists(DB_FILE):
        actors = ["Zoom", "Umarbek", "AMIN", "Bexruz", "Komron", "Shabnam", "Kamilla", "Tarjimon", "Feniks"]
        df = pd.DataFrame({
            "Ism": actors, "Ishladi": [0]*9, "To'landi": [0]*9,
            "Telegram_ID": [0]*9, "Parol": [str(random.randint(1000, 9999)) for _ in range(9)]
        })
        df.loc[df["Ism"] == "Feniks", "Telegram_ID"] = ADMIN_ID
        df.to_csv(DB_FILE, index=False)
    return pd.read_csv(DB_FILE)

def load_projects():
    if not os.path.exists(PROJECTS_FILE):
        df = pd.DataFrame(columns=["Loyiha", "Aktyor", "Narx"])
        df.to_csv(PROJECTS_FILE, index=False)
    return pd.read_csv(PROJECTS_FILE)

def load_custom_menu():
    if not os.path.exists(MENU_FILE):
        df = pd.DataFrame(columns=["Tugma_Nomi", "Xabar"])
        df.to_csv(MENU_FILE, index=False)
    return pd.read_csv(MENU_FILE)

def load_tasks():
    if not os.path.exists(TASKS_FILE):
        df = pd.DataFrame(columns=["ID", "Matn"])
        df.to_csv(TASKS_FILE, index=False)
    return pd.read_csv(TASKS_FILE)

def load_texts():
    if not os.path.exists(TEXTS_FILE):
        defaults = {
            "moliya": "📊 **STUDIYA UMUMIY HISOBOTI**",
            "parol": "🔑 **Aktyorlar PIN-kodlari:**",
            "ovoz": "📥 **Material topshirish qo'llanmasi:**\n\nBotga istalgan formatdagi faylni yuborishingiz mumkin:\n🎙 **Aktyorlar:** Voice, MP3, WAV, FLAC, MP4, ZIP, RAR.\n📝 **Tarjimonlar:** SRT, ASS, VTT, TXT yoki shunchaki oddiy matn.\n\nFayl yoki matnni yuboring, bot avtomatik loyihani so'raydi!",
            "vazifa_yoq": "🎉 Hozircha yangi vazifalar yo'q. Dam oling!",
            "vazifa_bor": "📌 **STUDIYA VAZIFALARI:**",
            "start_admin": "👑 Xush kelibsiz, Rejissyor!",
            "start_actor": "🎧 Salom! Ishga tayyormisiz?"
        }
        df = pd.DataFrame(list(defaults.items()), columns=["Key", "Matn"])
        df.to_csv(TEXTS_FILE, index=False)
    return pd.read_csv(TEXTS_FILE)

def get_text(key):
    df = load_texts()
    try: return df.loc[df["Key"] == key, "Matn"].values[0]
    except: return "Matn topilmadi"

def save_df(df, file):
    df.to_csv(file, index=False)

# ==========================================
# 🎛 ASOSIY MENYU 
# ==========================================
def main_menu(user_id):
    markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    custom_df = load_custom_menu()
    
    if user_id == ADMIN_ID:
        markup.add("📊 Moliya", "➕ Hisob-Kitob")
        markup.add("🎬 Loyihalar", "👤 Aktyor Qo'shish")
        markup.add("🔑 Parollar", "📁 Excel")
        markup.add("📝 Vazifa Qo'shish", "🛠 Menu Builder")
        markup.add("🔤 Tizim Matnlari")
    else:
        markup.add("🎙 Ovoz topshirish", "💰 Mening Hisobim")
        markup.add("📋 Faol Vazifalar")
        
    custom_buttons = custom_df["Tugma_Nomi"].tolist()
    if custom_buttons: markup.add(*custom_buttons)
    return markup

# ==========================================
# 🚀 START VA TIZIMGA KIRISH
# ==========================================
@bot.message_handler(commands=['start'])
def start(message):
    df = load_data()
    user_id = message.from_user.id
    head = "🎬 **UZDUBGO STUDIO | ELITE v11.0**\n" + "━" * 25 + "\n"
    
    if user_id == ADMIN_ID:
        bot.send_message(message.chat.id, head + get_text("start_admin"), reply_markup=main_menu(user_id))
    elif user_id in df["Telegram_ID"].values:
        actor = df.loc[df["Telegram_ID"] == user_id, "Ism"].values[0]
        bot.send_message(message.chat.id, head + f"👤 **{actor}**, " + get_text("start_actor"), reply_markup=main_menu(user_id))
    else:
        bot.send_message(message.chat.id, head + "🔐 Tizimga kirish uchun 4 xonali PIN-kodni yuboring:")

@bot.message_handler(func=lambda m: m.text and m.text.isdigit() and len(m.text) == 4)
def login(message):
    df = load_data()
    parollar = df["Parol"].astype(str).tolist()
    if message.text in parollar:
        actor = df.loc[df["Parol"].astype(str) == message.text, "Ism"].values[0]
        df.loc[df["Parol"].astype(str) == message.text, "Telegram_ID"] = message.from_user.id
        save_df(df, DB_FILE)
        bot.send_message(message.chat.id, f"✅ Tizimga kirdingiz, {actor}!", reply_markup=main_menu(message.from_user.id))
    else:
        bot.send_message(message.chat.id, "❌ PIN-kod xato.")

# ==========================================
# 🛠 ADMIN FUNKSIYALAR VA MATNLAR (Qisqartirilgan)
# ==========================================
@bot.message_handler(func=lambda m: m.text == "🔤 Tizim Matnlari" and m.from_user.id == ADMIN_ID)
def edit_texts_start(message):
    markup = types.InlineKeyboardMarkup(row_width=1)
    names = {"moliya": "📊 Moliya", "parol": "🔑 Parollar", "ovoz": "📥 Material yuborish", "vazifa_yoq": "📋 Vazifa yo'q", "vazifa_bor": "📋 Vazifa bor", "start_admin": "🚀 Start (Admin)", "start_actor": "🚀 Start (Aktyor)"}
    for key, val in names.items(): markup.add(types.InlineKeyboardButton(val, callback_data=f"edittext_{key}"))
    bot.send_message(message.chat.id, "🔤 **Matnni tanlang:**", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("edittext_"))
def edit_text_step1(call):
    key = call.data.split("_")[1]
    msg = bot.send_message(call.message.chat.id, f"📌 **Joriy matn:**\n_{get_text(key)}_\n\n✏️ **Yangi matnni yuboring:**")
    bot.register_next_step_handler(msg, lambda m: edit_text_step2(m, key))

def edit_text_step2(message, key):
    df = load_texts()
    df.loc[df["Key"] == key, "Matn"] = message.text
    save_df(df, TEXTS_FILE)
    bot.send_message(message.chat.id, "✅ Matn yangilandi!")

@bot.message_handler(func=lambda m: m.text == "🛠 Menu Builder" and m.from_user.id == ADMIN_ID)
def builder_start(message):
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("➕ Yangi Tugma", callback_data="add_btn"), types.InlineKeyboardButton("🗑 O'chirish", callback_data="del_btn"))
    bot.send_message(message.chat.id, "🎛 **Menu Builder:**", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data in ["add_btn", "del_btn"])
def btn_actions(call):
    if call.data == "add_btn":
        msg = bot.send_message(call.message.chat.id, "Tugma nomini yozing:")
        bot.register_next_step_handler(msg, lambda m: bot.register_next_step_handler(bot.send_message(m.chat.id, "Matn yozing:"), add_button_save, m.text))
    else:
        df = load_custom_menu()
        if df.empty: return bot.send_message(call.message.chat.id, "Tugmalar yo'q.")
        markup = types.InlineKeyboardMarkup()
        for btn in df["Tugma_Nomi"]: markup.add(types.InlineKeyboardButton(f"❌ {btn}", callback_data=f"delbtn_{btn}"))
        bot.send_message(call.message.chat.id, "O'chiramiz:", reply_markup=markup)

def add_button_save(message, btn_name):
    save_df(pd.concat([load_custom_menu(), pd.DataFrame({"Tugma_Nomi": [btn_name], "Xabar": [message.text]})], ignore_index=True), MENU_FILE)
    bot.send_message(message.chat.id, f"✅ '{btn_name}' qo'shildi! /start bosing.")

@bot.callback_query_handler(func=lambda call: call.data.startswith("delbtn_"))
def del_button_save(call):
    btn_name = call.data.split("_", 1)[1]
    df = load_custom_menu()
    save_df(df[df["Tugma_Nomi"] != btn_name], MENU_FILE)
    bot.send_message(call.message.chat.id, f"✅ O'chirildi. /start bosing.")

@bot.message_handler(func=lambda m: m.text in ["📝 Vazifa Qo'shish", "👤 Aktyor Qo'shish", "🎬 Loyihalar", "➕ Hisob-Kitob"] and m.from_user.id == ADMIN_ID)
def admin_commands(message):
    if message.text == "📝 Vazifa Qo'shish":
        markup = types.InlineKeyboardMarkup().add(types.InlineKeyboardButton("🗑 Tozalash", callback_data="clear_tasks"))
        bot.register_next_step_handler(bot.send_message(message.chat.id, "Vazifani yozing:", reply_markup=markup), lambda m: save_df(pd.concat([load_tasks(), pd.DataFrame({"ID": [len(load_tasks())+1], "Matn": [m.text]})], ignore_index=True), TASKS_FILE) if m.text else None)
    elif message.text == "👤 Aktyor Qo'shish":
        bot.register_next_step_handler(bot.send_message(message.chat.id, "Ismini yozing:"), lambda m: bot.send_message(m.chat.id, f"✅ Aktyor qo'shildi!\n🔐 PIN: `{str(random.randint(1000, 9999))}`") if not save_df(pd.concat([load_data(), pd.DataFrame({"Ism": [m.text], "Ishladi": [0], "To'landi": [0], "Telegram_ID": [0], "Parol": [str(random.randint(1000, 9999))]})], ignore_index=True), DB_FILE) else "")
    elif message.text == "🎬 Loyihalar":
        markup = types.InlineKeyboardMarkup().add(types.InlineKeyboardButton("➕ Yangi Loyiha", callback_data="add_p"))
        bot.send_message(message.chat.id, "Loyihalar:\n" + "".join([f"🔸 {p}\n" for p in load_projects()["Loyiha"].unique()]), reply_markup=markup)
    elif message.text == "➕ Hisob-Kitob":
        markup = types.InlineKeyboardMarkup()
        for _, r in load_data().iterrows():
            if r["Ism"] != "Feniks": markup.add(types.InlineKeyboardButton(f"{r['Ism']} ({int(r['Ishladi'])-int(r['To\'landi']):,})", callback_data=f"payto_{r['Ism']}"))
        bot.send_message(message.chat.id, "Aktyorni tanlang:", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data == "clear_tasks")
def clr_tsk(c): save_df(pd.DataFrame(columns=["ID", "Matn"]), TASKS_FILE); bot.send_message(c.message.chat.id, "✅ O'chirildi.")

@bot.callback_query_handler(func=lambda call: call.data == "add_p")
def add_p(c): bot.register_next_step_handler(bot.send_message(c.message.chat.id, "Loyiha nomini yozing:"), lambda m: bot.send_message(m.chat.id, "Narx belgilang:", reply_markup=types.InlineKeyboardMarkup().add(*[types.InlineKeyboardButton(a, callback_data=f"setrate_{m.text}_{a}") for a in load_data()["Ism"] if a != "Feniks"], types.InlineKeyboardButton("✅ TUGATISH", callback_data="done"))))

@bot.callback_query_handler(func=lambda call: call.data.startswith("setrate_"))
def set_r(c): bot.register_next_step_handler(bot.send_message(c.message.chat.id, f"💰 **{c.data.split('_')[2]}** narxi:"), lambda m: (save_df(pd.concat([load_projects()[~((load_projects()["Loyiha"] == c.data.split('_')[1]) & (load_projects()["Aktyor"] == c.data.split('_')[2]))], pd.DataFrame({"Loyiha": [c.data.split('_')[1]], "Aktyor": [c.data.split('_')[2]], "Narx": [int(m.text)]})], ignore_index=True), PROJECTS_FILE), bot.send_message(m.chat.id, "✅ Saqlandi.")))

@bot.callback_query_handler(func=lambda call: call.data == "done")
def done_p(c): bot.delete_message(c.message.chat.id, c.message.message_id)

@bot.callback_query_handler(func=lambda call: call.data.startswith("payto_"))
def pay_to(c): bot.register_next_step_handler(bot.send_message(c.message.chat.id, "Summa yozing:"), lambda m: pay_fin(m, c.data.split('_')[1]))

def pay_fin(message, actor):
    df = load_data(); summa = int(message.text)
    df.loc[df["Ism"] == actor, "To'landi"] += summa; save_df(df, DB_FILE)
    bot.send_message(ADMIN_ID, f"✅ Saqlandi! {actor}: {summa:,}")
    actor_id = df.loc[df["Ism"] == actor, "Telegram_ID"].values[0]
    if actor_id != 0: bot.send_message(actor_id, f"💸 To'lov: {summa:,}" if summa > 0 else f"📉 Ushlab qolindi: {summa:,}")

@bot.message_handler(func=lambda m: m.text in ["📊 Moliya", "🔑 Parollar", "📁 Excel"] and m.from_user.id == ADMIN_ID)
def admin_reports(message):
    if message.text == "📊 Moliya":
        bot.send_message(message.chat.id, get_text("moliya") + "\n\n" + "".join([f"👤 {r['Ism']}: {int(r['Ishladi']) - int(r['To\'landi']):,} so'm\n" for _, r in load_data().iterrows() if r["Ism"] != "Feniks"]))
    elif message.text == "🔑 Parollar":
        bot.send_message(message.chat.id, get_text("parol") + "\n\n" + "".join([f"👤 {r['Ism']}: `{r['Parol']}` ({'🟢' if r['Telegram_ID'] != 0 else '🔴'})\n" for _, r in load_data().iterrows() if r["Ism"] != "Feniks"]))
    elif message.text == "📁 Excel":
        load_data().to_excel("Uzdubgo_Hisobot.xlsx", index=False)
        with open("Uzdubgo_Hisobot.xlsx", "rb") as f: bot.send_document(message.chat.id, f)

@bot.message_handler(func=lambda m: m.text in ["🎙 Ovoz topshirish", "💰 Mening Hisobim", "📋 Faol Vazifalar"])
def actor_menus(message):
    if message.text == "🎙 Ovoz topshirish": bot.send_message(message.chat.id, get_text("ovoz"))
    elif message.text == "💰 Mening Hisobim":
        row = load_data()[load_data()["Telegram_ID"] == message.from_user.id].iloc[0]
        bot.send_message(message.chat.id, f"👤 **{row['Ism']}**\n\n🎬 Ishlagan: {int(row['Ishladi']):,}\n💸 Olgan: {int(row['To\'landi']):,}\n🔴 Qarz: {int(row['Ishladi'])-int(row['To\'landi']):,}")
    elif message.text == "📋 Faol Vazifalar":
        df = load_tasks()
        bot.send_message(message.chat.id, get_text("vazifa_yoq") if df.empty else get_text("vazifa_bor") + "\n\n" + "".join([f"🔸 {r['Matn']}\n\n" for _, r in df.iterrows()]))

# ==========================================
# 📥 YANGI: UNIVERSAL QABUL QILISH TIZIMI
# ==========================================
def is_valid_submission(message):
    if message.content_type in ['voice', 'audio', 'document', 'video']: return True
    if message.content_type == 'text':
        if message.text.startswith('/'): return False
        custom_btns = load_custom_menu()["Tugma_Nomi"].tolist()
        if message.text in STATIC_BUTTONS or message.text in custom_btns: return False
        df = load_data()
        if message.from_user.id in df["Telegram_ID"].values: return True
    return False

user_submission_cache = {}

@bot.message_handler(func=is_valid_submission, content_types=['voice', 'audio', 'document', 'video', 'text'])
def handle_all_submissions(message):
    df = load_data()
    if message.from_user.id not in df["Telegram_ID"].values: return
    actor = df.loc[df["Telegram_ID"] == message.from_user.id, "Ism"].values[0]
    
    user_submission_cache[message.from_user.id] = {'msg': message, 'actor': actor}
    my_projects = load_projects()[load_projects()["Aktyor"] == actor]["Loyiha"].unique()
    
    markup = types.InlineKeyboardMarkup(row_width=2)
    for p in my_projects: markup.add(types.InlineKeyboardButton(p, callback_data=f"dub_{p}"))
        
    if len(my_projects) == 0: 
        bot.send_message(message.chat.id, "❌ Sizga stavka belgilanmagan.")
    else:
        # Fayl turini aniqlaymiz
        if message.content_type == 'text': turi = "📝 Matn/Tarjima"
        elif message.content_type == 'document': turi = "📄 Hujjat/Arxiv"
        elif message.content_type == 'video': turi = "🎞 Video fayl"
        else: turi = "🎙 Ovozli fayl"
        
        bot.send_message(message.chat.id, f"✅ {turi} qabul qilindi!\n🎤 Qaysi loyiha uchun?", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("dub_"))
def process_submission_step2(call):
    p = call.data.split("_")[1]
    user_submission_cache[call.from_user.id]['project'] = p
    bot.delete_message(call.message.chat.id, call.message.message_id)
    bot.register_next_step_handler(bot.send_message(call.message.chat.id, f"🔢 '{p}' nechinchi qismi?"), final_submission_process)

def final_submission_process(message):
    try:
        data = user_submission_cache[message.from_user.id]
        pr_df = load_projects()
        rate = int(pr_df[(pr_df["Loyiha"] == data['project']) & (pr_df["Aktyor"] == data['actor'])]["Narx"].values[0])
        
        df = load_data()
        df.loc[df["Ism"] == data['actor'], "Ishladi"] += rate
        save_df(df, DB_FILE)
        
        msg_obj = data['msg']
        cap = f"📥 **YANGI MATERIAL**\n━━━━━━━━━━━━━━━━━━━━\n🎬 **Loyiha:** {data['project']}\n👤 **Muallif:** {data['actor']}\n🔢 **Qism:** {message.text}\n💰 **Smeta:** {rate:,} so'm yozildi\n━━━━━━━━━━━━━━━━━━━━\n#{data['project'].replace(' ', '')}"
        
        # Kanalga to'g'ri turdagi faylni uzatish
        if msg_obj.content_type == 'voice': bot.send_voice(CHANNEL_ID, msg_obj.voice.file_id, caption=cap)
        elif msg_obj.content_type == 'audio': bot.send_audio(CHANNEL_ID, msg_obj.audio.file_id, caption=cap)
        elif msg_obj.content_type == 'document': bot.send_document(CHANNEL_ID, msg_obj.document.file_id, caption=cap)
        elif msg_obj.content_type == 'video': bot.send_video(CHANNEL_ID, msg_obj.video.file_id, caption=cap)
        elif msg_obj.content_type == 'text': bot.send_message(CHANNEL_ID, f"{cap}\n\n📝 **Yuborilgan Tarjima / Matn:**\n\n{msg_obj.text}")

        bot.send_message(message.chat.id, f"✅ Kanalga yuborildi! Hisobingizga {rate:,} so'm qo'shildi.")
        del user_submission_cache[message.from_user.id]
    except Exception as e: bot.send_message(message.chat.id, "⚠️ Xatolik yuz berdi. Qaytadan urinib ko'ring.")

# ==========================================
# 🧲 DINAMIK TUGMALARNI ESHITISH
# ==========================================
@bot.message_handler(func=lambda m: True)
def handle_custom_buttons(message):
    custom_df = load_custom_menu()
    if message.text in custom_df["Tugma_Nomi"].values:
        bot.send_message(message.chat.id, custom_df.loc[custom_df["Tugma_Nomi"] == message.text, "Xabar"].values[0])

# ==========================================
# 🌐 SERVER
# ==========================================
@app.route('/')
def home(): return "Uzdubgo Elite v11.0 is Online!"

if __name__ == "__main__":
    bot.remove_webhook()
    threading.Thread(target=lambda: bot.infinity_polling(skip_pending=True)).start()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
    
