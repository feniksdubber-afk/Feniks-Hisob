import telebot
import pandas as pd

# BotFather'dan olingan token
TOKEN = '6844735110:AAHybqfU2qnfxXuy7MGUG-VxvMWs3aP_5f8'
bot = telebot.TeleBot(TOKEN)

# 1. Barcha ma'lumotlarni bazaga kiritamiz
# Eslatma: 'To'landi' so'zi xato bermasligi uchun qatorlar " " ichiga olindi
data = {
    "Ism": ["Zoom", "Umarbek", "AMIN", "Bexruz", "Komron", "Shabnam", "Kamilla", "Tarjimon", "Feniks"],
    "Ishladi": [1400000, 300000, 200000, 400000, 400000, 200000, 200000, 100000, 2360000],
    "To'landi": [700000, 200000, 150000, 400000, 400000, 100000, 100000, 0, 2360000]
}
df = pd.DataFrame(data)

# 2. Start va Hisobot buyrug'i
@bot.message_handler(commands=['start', 'hisobot'])
def send_report(message):
    # Qarzni hisoblash
    df["Qarz"] = df["Ishladi"] - df["To'landi"]
    
    msg = "📊 **UZDUBGO JORIY HISOBOT**\n"
    msg += "--------------------------------\n"
    
    for _, row in df.iterrows():
        status = "✅" if row["Qarz"] <= 0 else "❌"
        msg += f"{status} **{row['Ism']}**: {row['Qarz']:,} so'm\n"
    
    # Feniks (Siz) dan tashqari jami qarzni hisoblash
    total_debt = df.loc[df["Ism"] != "Feniks", "Qarz"].sum()
    
    msg += "--------------------------------\n"
    msg += f"🔴 **Jami tarqatilishi kerak: {total_debt:,} so'm**\n"
    msg += "--------------------------------\n"
    msg += "✍️ To'lov kiritish uchun: `Ism Summa`\n"
    msg += "*(Misol: Zoom 100000)*"
    
    bot.reply_to(message, msg, parse_mode="Markdown")

# 3. To'lov kiritish (Oddiy matn orqali)
@bot.message_handler(func=lambda message: True)
def handle_payment(message):
    global df
    try:
        text = message.text.split()
        if len(text) != 2:
            return
            
        target_name = text[0].capitalize()
        amount = int(text[1])
        
        if target_name in df["Ism"].values:
            # To'lovni hisoblash va jadvalni yangilash
            df.loc[df["Ism"] == target_name, "To'landi"] += amount
            df["Qarz"] = df["Ishladi"] - df["To'landi"]
            
            new_debt = df.loc[df["Ism"] == target_name, "Qarz"].values[0]
            
            bot.reply_to(message, 
                f"✅ **Muvaffaqiyatli!**\n\n"
                f"👤 {target_name}ga {amount:,} so'm kiritildi.\n"
                f"📉 Qolgan qarz: {new_debt:,} so'm", 
                parse_mode="Markdown")
        else:
            bot.reply_to(message, "⚠️ Ism topilmadi! Ro'yxatdagi ismlardan foydalaning.")
            
    except ValueError:
        bot.reply_to(message, "⚠️ Iltimos, summani faqat raqamlarda yozing.")
    except Exception as e:
        bot.reply_to(message, f"⚠️ Xatolik: {str(e)}")

print("Bot ishga tushdi...")
bot.polling()
