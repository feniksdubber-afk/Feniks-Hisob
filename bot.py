import telebot
from telebot import types
import os
import threading
from flask import Flask

# O'zimiz yaratgan qismlarni (modullarni) chaqirib olamiz
from config import *
from database import *
import admin
import employee

bot = telebot.TeleBot(TOKEN, parse_mode="Markdown")
app = Flask(__name__)

# ==========================================
# 🎛 MENYU VA START (KIRISH QISMI)
# ==========================================
def main_menu(user_id):
    df = load_data()
    row = df[df["Telegram_ID"] == user_id].iloc[0]
    lavozim = row["Lavozim"]
    
    markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    custom_df = load_custom_menu()
    
    if lavozim == "Admin":
        markup.add("📊 Moliya", "💸 Ishchilarga pul tashlash")
        markup.add("🎬 Loyihalar", "👤 Xodim Qo'shish", "👤 Xodimni O'chirish")
        markup.add("📣 E'lon Yuborish", "🔑 Parollar")
        markup.add("📝 Vazifa Qo'shish", "🛠 Menu Builder")
        markup.add("🔤 Tizim Matnlari", "📁 Excel", "🔐 Parolni o'zgartirish")
    elif lavozim == "Audio montajchi":
        markup.add("🎧 Tayyor Material Yuborish", "💰 Mening Hisobim")
        markup.add("📋 Faol Vazifalar", "💬 Adminga Savol/Xabar")
        markup.add("🔐 Parolni o'zgartirish")
    elif lavozim == "Elon yozishchi":
        markup.add("✍️ Tayyor Elonni yuborish", "💰 Mening Hisobim")
        markup.add("📋 Faol Vazifalar", "💬 Adminga Savol/Xabar")
        markup.add("🔐 Parolni o'zgartirish")
    else:
        markup.add("🎙 Ovoz/Material topshirish", "💰 Mening Hisobim")
        markup.add("📋 Faol Vazifalar", "💬 Adminga Savol/Xabar")
        markup.add("🔐 Parolni o'zgartirish")
        
    for btn in custom_df["Tugma_Nomi"]: markup.add(btn)
    return markup

@bot.message_handler(commands=['start'])
def start(message):
    df = load_data()
    user_id = message.from_user.id
    bot.clear_step_handler_by_chat_id(message.chat.id)
    head = "🎬 **FENIKS STUDIO | ELITE v12.0**\n" + "━" * 25 + "\n"
    
    if user_id in df["Telegram_ID"].values:
        row = df[df["Telegram_ID"] == user_id].iloc[0]
        if row["Lavozim"] == "Admin": 
            bot.send_message(message.chat.id, head + get_text("start_admin"), reply_markup=main_menu(user_id))
        else: 
            bot.send_message(message.chat.id, head + f"👤 **{row['Ism']}** ({row['Lavozim']}),\n\n" + get_text("start_actor"), reply_markup=main_menu(user_id))
    else:
        welcome_msg = (
            "👋 **Xush kelibsiz!**\n\n"
            "Siz **Feniks Studio**ning rasmiy yopiq ishchi tizimiga kirdingiz.\n\n"
            "⛔️ *Diqqat: Bu bot faqatgina studiyamizning rasmiy xodimlari uchun mo'ljallangan.*\n\n"
            "Agar siz studiya xodimi bo'lsangiz, tizimga kirish uchun Admindan olingan **4 xonali PIN-kodni** yuboring."
        )
        bot.send_message(message.chat.id, head + welcome_msg)

@bot.message_handler(func=lambda m: m.text and m.text.isdigit() and len(m.text) == 4)
def login(message):
    df = load_data()
    parollar = df["Parol"].astype(str).tolist()
    if message.text in parollar:
        actor = df.loc[df["Parol"].astype(str) == message.text, "Ism"].values[0]
        df.loc[df["Parol"].astype(str) == message.text, "Telegram_ID"] = message.from_user.id
        save_df(df, DB_FILE)
        bot.send_message(message.chat.id, f"✅ Tizimga muvaffaqiyatli kirdingiz, {actor}!", reply_markup=main_menu(message.from_user.id))
    else:
        bot.send_message(message.chat.id, "❌ PIN-kod xato! Iltimos, qaytadan urinib ko'ring yoki Admin bilan bog'laning.")

@bot.message_handler(func=lambda m: m.text == "🔐 Parolni o'zgartirish")
def change_pass_start(message):
    bot.clear_step_handler_by_chat_id(message.chat.id)
    bot.register_next_step_handler(bot.send_message(message.chat.id, "✏️ **Yangi 4 xonali PIN-kod yozing:**\n*(Faqat raqam)*"), change_pass_save)

def change_pass_save(message):
    if message.text.isdigit() and len(message.text) == 4:
        df = load_data()
        df.loc[df["Telegram_ID"] == message.from_user.id, "Parol"] = message.text
        save_df(df, DB_FILE)
        bot.send_message(message.chat.id, f"✅ Parolingiz o'zgardi! Yangi parolingiz: `{message.text}`")
    else:
        bot.send_message(message.chat.id, "⚠️ Xato! Parol aynan 4 ta raqam bo'lishi shart. Boshidan urining.")

# ==========================================
# 🧲 BOSHQA MODULLARNI ULLASH
# ==========================================
# Admin va Xodim funksiyalarini shu yerda botga ulab qo'yamiz
admin.register_admin_handlers(bot)
employee.register_employee_handlers(bot)

# Menyu builder dinamik tugmalari uchun handler (eng oxirida turishi kerak)
@bot.message_handler(func=lambda m: True)
def handle_custom_buttons(message):
    custom_df = load_custom_menu()
    if message.text in custom_df["Tugma_Nomi"].values:
        bot.send_message(message.chat.id, custom_df.loc[custom_df["Tugma_Nomi"] == message.text, "Xabar"].values[0])

# ==========================================
# 🌐 SERVERNI YOQISH (RENDER UCHUN)
# ==========================================
@app.route('/')
def home(): 
    return "FeniksStudio Elite v12.0 (Modular Pro) is Online 24/7!"

if __name__ == "__main__":
    bot.remove_webhook()
    # infinity_polling orqali botni qotmasdan ishlashini ta'minlaymiz
    threading.Thread(target=lambda: bot.infinity_polling(skip_pending=True)).start()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
    
