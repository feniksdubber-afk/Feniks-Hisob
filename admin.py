import pandas as pd
from telebot import types
from config import *
from database import *

payment_cache = {}
admin_reply_cache = {}

def register_admin_handlers(bot):
    # --- MOLIYA VA HISOBOTLAR ---
    @bot.message_handler(func=lambda m: m.text in ["📊 Moliya", "🔑 Parollar", "📁 Excel"] and m.from_user.id == ADMIN_ID)
    def admin_reports(message):
        df = load_data()
        if message.text == "📊 Moliya":
            txt = get_text("moliya") + "\n\n"
            for _, r in df.iterrows():
                if r["Lavozim"] != "Admin": txt += f"👤 {r['Ism']} ({r['Lavozim']}): {int(r['Ishladi']) - int(r['To\'landi']):,} so'm\n"
            bot.send_message(message.chat.id, txt)
        elif message.text == "🔑 Parollar":
            txt = get_text("parol") + "\n\n"
            for _, r in df.iterrows():
                if r["Lavozim"] != "Admin": txt += f"👤 {r['Ism']}: `{r['Parol']}` ({'🟢' if r['Telegram_ID'] != 0 else '🔴'})\n"
            bot.send_message(message.chat.id, txt)
        elif message.text == "📁 Excel":
            df.to_excel("Feniks_Hisobot.xlsx", index=False)
            with open("Feniks_Hisobot.xlsx", "rb") as f: bot.send_document(message.chat.id, f)

    # --- ISHCHILARGA PUL TO'LASH ---
    @bot.message_handler(func=lambda m: m.text == "💸 Ishchilarga pul tashlash" and m.from_user.id == ADMIN_ID)
    def pay_init(message):
        markup = types.InlineKeyboardMarkup(row_width=2)
        added = False
        for _, r in load_data().iterrows():
            if r["Lavozim"] != "Admin":
                b = int(r["Ishladi"]) - int(r["To'landi"])
                markup.add(types.InlineKeyboardButton(f"{r['Ism']} ({b:,})", callback_data=f"payto_{r['Ism']}"))
                added = True
        if added: bot.send_message(message.chat.id, "💳 Pul o'tkaziladigan xodimni tanlang:", reply_markup=markup)
        else: bot.send_message(message.chat.id, "❌ Xodimlar yo'q.")

    @bot.callback_query_handler(func=lambda call: call.data.startswith("payto_"))
    def pay_step1(call):
        actor = call.data.split("_")[1]
        row = load_data()[load_data()["Ism"] == actor].iloc[0]
        balans = int(row["Ishladi"]) - int(row["To'landi"])
        payment_cache[call.from_user.id] = {'actor': actor, 'karta': row["Karta"], 'balans': balans}
        bot.clear_step_handler_by_chat_id(call.message.chat.id)
        msg = bot.send_message(call.message.chat.id, f"👤 **{actor}**\n💳 Karta: `{row['Karta']}`\n💰 Balans: {balans:,}\n\nSummani raqamda yozing:")
        bot.register_next_step_handler(msg, pay_step2)

    def pay_step2(message):
        if not message.text.isdigit(): return bot.send_message(message.chat.id, "⚠️ Faqat raqam kiriting!")
        payment_cache[message.from_user.id]['summa'] = int(message.text)
        bot.register_next_step_handler(bot.send_message(message.chat.id, "📝 Qaysi loyiha/sabab?"), pay_step3)

    def pay_step3(message):
        payment_cache[message.from_user.id]['sabab'] = message.text
        bot.register_next_step_handler(bot.send_message(message.chat.id, "📸 Chek rasmini yuboring:"), pay_step4)

    def pay_step4(message):
        if message.content_type != 'photo': return bot.send_message(message.chat.id, "⚠️ Rasm emas! Bekor qilindi.")
        data = payment_cache[message.from_user.id]
        df = load_data()
        df.loc[df["Ism"] == data['actor'], "To'landi"] += data['summa']
        save_df(df, DB_FILE)
        
        actor_id = df.loc[df["Ism"] == data['actor'], "Telegram_ID"].values[0]
        if actor_id != 0:
            caption = f"🎉 **To'lov qabul qildingiz!**\n💰 Summa: {data['summa']:,} so'm\n🎬 Sabab: {data['sabab']}\n💼 Qolgan balans: {data['balans'] - data['summa']:,} so'm"
            try: bot.send_photo(actor_id, message.photo[-1].file_id, caption=caption)
            except: pass
        bot.send_message(message.chat.id, f"✅ To'lov saqlandi! ({data['actor']})")
        del payment_cache[message.from_user.id]

    # --- SHAXSIY VAZIFA QO'SHISH (YANGI) ---
    @bot.message_handler(func=lambda m: m.text == "📝 Vazifa Qo'shish" and m.from_user.id == ADMIN_ID)
    def task_start(message):
        bot.clear_step_handler_by_chat_id(message.chat.id)
        msg = bot.send_message(message.chat.id, "📝 Yangi vazifa matnini yozing:\n*(Vazifalarni tozalash uchun /clear_tasks yozing)*")
        bot.register_next_step_handler(msg, task_ask_who)

    def task_ask_who(message):
        if message.text == '/clear_tasks':
            save_df(pd.DataFrame(columns=["ID", "Matn", "Kimga"]), TASKS_FILE)
            return bot.send_message(message.chat.id, "✅ Barcha vazifalar tozalandi.")
        
        admin_reply_cache[message.from_user.id] = {'task_text': message.text}
        markup = types.InlineKeyboardMarkup(row_width=2)
        markup.add(types.InlineKeyboardButton("📢 Hammaga (Umumiy)", callback_data="taskto_Hammaga"))
        for actor in load_data()["Ism"]:
            if actor != "Feniks": markup.add(types.InlineKeyboardButton(f"👤 {actor}", callback_data=f"taskto_{actor}"))
        bot.send_message(message.chat.id, "Biriktiramiz: Bu vazifa kim uchun?", reply_markup=markup)

    @bot.callback_query_handler(func=lambda call: call.data.startswith("taskto_"))
    def task_save(call):
        kimga = call.data.split("_")[1]
        text = admin_reply_cache[call.from_user.id]['task_text']
        df = load_tasks()
        new_row = pd.DataFrame({"ID": [len(df)+1], "Matn": [text], "Kimga": [kimga]})
        save_df(pd.concat([df, new_row], ignore_index=True), TASKS_FILE)
        bot.edit_message_text(f"✅ Vazifa '{kimga}' ga muvaffaqiyatli biriktirildi!", call.message.chat.id, call.message.message_id)

    # --- XODIM XATIGA JAVOB YAZISH (YANGI) ---
    @bot.callback_query_handler(func=lambda call: call.data.startswith("replyto_"))
    def admin_reply_to_employee(call):
        user_id = int(call.data.split("_")[1])
        bot.clear_step_handler_by_chat_id(call.message.chat.id)
        msg = bot.send_message(call.message.chat.id, "✍️ Xodimga javobingizni yozing:")
        bot.register_next_step_handler(msg, lambda m: send_reply_to_emp(m, user_id))

    def send_reply_to_emp(message, user_id):
        try:
            bot.send_message(user_id, f"👑 **Rejissyordan Javob:**\n\n{message.text}")
            bot.send_message(message.chat.id, "✅ Javobingiz xodimga yetkazildi.")
        except:
            bot.send_message(message.chat.id, "❌ Xatolik: Xodim botni bloklagan bo'lishi mumkin.")
      
