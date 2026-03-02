import telebot
import pandas as pd
import os
import threading
from flask import Flask

# BotFather'dan olingan token
TOKEN = '6844735110:AAHybqfU2qnfxXuy7MGUG-VxvMWs3aP_5f8'
bot = telebot.TeleBot(TOKEN)

# Render qidirayotgan "Veb-sayt"
app = Flask(__name__)

# 1. Barcha ma'lumotlarni bazaga kiritamiz
data = {
    "Ism": ["Zoom", "Umarbek", "AMIN", "Bexruz", "Komron", "Shabnam", "Kamilla", "Tarjimon", "Feniks"],
    "Ishladi": [1400000, 300000, 200000, 400000, 400000, 200000, 200000, 100000, 2360000],
    "To'landi": [700000, 200000, 150000, 400000, 400000, 100000, 100000, 0, 2360000]
}
df = pd.DataFrame(data)

@bot.message_handler(commands=['start', 'hisobot'])
def send_report(message):
    df["Qarz"] = df["Ishladi"] - df["To'landi"]
    msg = "📊 **UZDUBGO JORIY HISOBOT**\n--------------------------------\n"
    
    for _, row in df.iterrows():
        status = "✅" if row["Qarz"] <= 0 else "❌"
        msg += f"{status} **{row['Ism']}**: {row['Qarz']:,} so'm\n"
    
    total_debt = df.loc[df["Ism"] != "Feniks", "Qarz"].sum()
    msg += "--------------------------------\n"
    msg += f"🔴 **Jami tarqatilishi kerak: {total_debt:,} so'm**\n"
    msg += "--------------------------------\n"
    msg += "✍️ To'lov kiritish uchun: `Ism Summa`\n*(Misol: Zoom 100000)*"
    
    bot.reply_to(message, msg, parse_mode="Markdown")

@bot.message_handler(func=lambda message: True)
def handle_payment(message):
    global df
    try:
        text = message.text.split()
        if len(text) != 2: return
            
        target_name = text[0].capitalize()
        amount = int(text[1])
        
        if target_name in df["Ism"].values:
            df.loc[df["Ism"] == target_name, "To'landi"] += amount
            df["Qarz"] = df["Ishladi"] - df["To'landi"]
            new_debt = df.loc[df["Ism"] == target_name, "Qarz"].values[0]
            
            bot.reply_to(message, f"✅ **Muvaffaqiyatli!**\n\n👤 {target_name}ga {amount:,} so'm kiritildi.\n📉 Qolgan qarz: {new_debt:,} so'm", parse_mode="Markdown")
        else:
            bot.reply_to(message, "⚠️ Ism topilmadi! Ro'yxatdagi ismlardan foydalaning.")
    except ValueError:
        bot.reply_to(message, "⚠️ Iltimos, summani faqat raqamlarda yozing.")
    except Exception as e:
        bot.reply_to(message, f"⚠️ Xatolik: {str(e)}")

# Render uchun "Aldamchi" sahifa
@app.route('/')
def index():
    return "Uzdubgo Moliya Boti 100% ishlayapti!"

# Botni alohida oqimda ishga tushirish funksiyasi
def run_bot():
    bot.polling()

if __name__ == "__main__":
    # Botni orqa fonda yurgizamiz
    t = threading.Thread(target=run_bot)
    t.start()
    
    # Render so'ragan portni ochamiz
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
    
