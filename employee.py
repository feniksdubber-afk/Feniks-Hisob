import pandas as pd
from telebot import types
from config import *
from database import *

montajchi_cache = {}
user_submission_cache = {}

def register_employee_handlers(bot):

    # ==========================================
    # 💰 SHAXSIY HISOB VA KARTA
    # ==========================================
    @bot.message_handler(func=lambda m: m.text == "💰 Mening Hisobim")
    def my_acc(message):
        r = load_data()[load_data()["Telegram_ID"] == message.from_user.id].iloc[0]
        m = types.InlineKeyboardMarkup()
        m.add(types.InlineKeyboardButton("💳 Karta kiritish", callback_data="edit_card"), 
              types.InlineKeyboardButton("🗑 Nollash (0)", callback_data="clr_bal"))
        bot.send_message(message.chat.id, f"👤 **{r['Ism']}** ({r['Lavozim']})\n💰 Balans: {int(r['Ishladi'])-int(r['To\'landi']):,}\n💳 Karta: `{r['Karta']}`", reply_markup=m)

    @bot.callback_query_handler(func=lambda call: call.data == "edit_card")
    def ed_card(call): 
        bot.register_next_step_handler(bot.send_message(call.message.chat.id, "💳 Yangi karta raqam yozing:"), lambda m: (load_data().assign(Karta=lambda x: [m.text if tid == m.from_user.id else k for tid, k in zip(x['Telegram_ID'], x['Karta'])]).pipe(save_df, DB_FILE), bot.send_message(m.chat.id, f"✅ Saqlandi: `{m.text}`")))

    # TO'G'RILANGAN XATO 1: Balansni nollash funksiyasi qo'shildi!
    @bot.callback_query_handler(func=lambda call: call.data == "clr_bal")
    def clear_balance_req(call):
        df = load_data()
        df.loc[df["Telegram_ID"] == call.from_user.id, "Ishladi"] = 0
        df.loc[df["Telegram_ID"] == call.from_user.id, "To'landi"] = 0
        save_df(df, DB_FILE)
        bot.edit_message_text("✅ Balansingiz 0 ga tushirildi!", call.message.chat.id, call.message.message_id)

    # ==========================================
    # 📋 SHAXSIY VAZIFALARNI KO'RISH
    # ==========================================
    @bot.message_handler(func=lambda m: m.text == "📋 Faol Vazifalar")
    def show_tasks(message):
        df = load_data()
        if message.from_user.id not in df["Telegram_ID"].values: return
        my_name = df[df["Telegram_ID"] == message.from_user.id].iloc[0]["Ism"]
        
        tasks_df = load_tasks()
        my_tasks = tasks_df[(tasks_df["Kimga"] == "Hammaga") | (tasks_df["Kimga"] == my_name)]
        
        if my_tasks.empty: 
            bot.send_message(message.chat.id, get_text("vazifa_yoq"))
        else: 
            txt = "📌 **Siz uchun faol vazifalar:**\n\n"
            for _, r in my_tasks.iterrows(): 
                tur = "📢 Umumiy" if r["Kimga"] == "Hammaga" else "🎯 Shaxsiy"
                txt += f"[{tur}] 🔸 {r['Matn']}\n\n"
            bot.send_message(message.chat.id, txt)

    # ==========================================
    # 💬 ADMINGA SAVOL YUBORISH
    # ==========================================
    @bot.message_handler(func=lambda m: m.text == "💬 Adminga Savol/Xabar")
    def ask_admin_start(message):
        bot.clear_step_handler_by_chat_id(message.chat.id)
        msg = bot.send_message(message.chat.id, "📝 Qanday savol yoki muammoingiz bor? Matnni shu yerga yozib yuboring:")
        bot.register_next_step_handler(msg, send_to_admin)

    def send_to_admin(message):
        df = load_data()
        sender_name = df[df["Telegram_ID"] == message.from_user.id].iloc[0]["Ism"]
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("✉️ Javob yozish", callback_data=f"replyto_{message.from_user.id}"))
        bot.send_message(ADMIN_ID, f"📨 **XODIMDAN SAVOL/XABAR**\n━━━━━━━━━━━━━━━━━\n👤 **Kimdan:** {sender_name}\n\n💬 **Matn:** {message.text}", reply_markup=markup)
        bot.send_message(message.chat.id, "✅ Xabaringiz Rejissyorga yuborildi! Javobni bot orqali kutib oling.")

    # ==========================================
    # 📥 UNIVERSAL QABUL QILGICH VA MATERIAL TOPSHIRISH
    # ==========================================
    
    # TO'G'RILANGAN XATO 2: Aktyorlar tugmani bosa olishi ta'minlandi!
    @bot.message_handler(func=lambda m: m.text == "🎙 Ovoz/Material topshirish")
    def show_instruction_for_voice(message):
        bot.send_message(message.chat.id, get_text("ovoz"))

    @bot.message_handler(func=lambda m: m.text == "🎧 Tayyor Material Yuborish")
    def mon_start(message):
        montajchi_cache[message.from_user.id] = {'step': 'video'}
        bot.send_message(message.chat.id, "🎧 **Montajchi (1/2):** Avval **VIDEO** faylni yuboring:")

    def is_valid_sub(m):
        return m.content_type in ['voice', 'audio', 'document', 'video', 'text'] and m.text not in STATIC_BUTTONS and not str(m.text).startswith('/')

    @bot.message_handler(func=is_valid_sub, content_types=['voice', 'audio', 'document', 'video', 'text'])
    def handle_all_subs(message):
        df = load_data()
        if message.from_user.id not in df["Telegram_ID"].values: return
        r = df[df["Telegram_ID"] == message.from_user.id].iloc[0]
        actor = r["Ism"]; lavozim = r["Lavozim"]
        
        if lavozim == "Elon yozishchi" and message.content_type == 'text':
            bot.send_message(CHANNEL_ID, f"✍️ **YANGI E'LON**\n👤 Muallif: {actor}\n\n{message.text}")
            return bot.send_message(message.chat.id, "✅ E'lon kanalga ketdi!")

        if lavozim == "Audio montajchi" and message.from_user.id in montajchi_cache:
            st = montajchi_cache[message.from_user.id]
            if st['step'] == 'video' and message.content_type in ['video', 'document']:
                st['vid'] = message; st['step'] = 'audio'
                return bot.send_message(message.chat.id, "✅ Video olindi. Endi **AUDIO** faylini yuboring:")
            elif st['step'] == 'audio' and message.content_type in ['audio', 'voice', 'document']:
                st['aud'] = message
                m = types.InlineKeyboardMarkup()
                projs = load_projects()[load_projects()["Aktyor"] == actor]["Loyiha"].unique()
                if len(projs) == 0: return bot.send_message(message.chat.id, "❌ Sizga biriktirilgan loyihalar yo'q. Adminga murojaat qiling.")
                for p in projs: m.add(types.InlineKeyboardButton(p, callback_data=f"monsub_{p}"))
                return bot.send_message(message.chat.id, "🎬 Ikkala fayl olindi! Qaysi loyiha?", reply_markup=m)

        user_submission_cache[message.from_user.id] = {'msg': message, 'actor': actor}
        m = types.InlineKeyboardMarkup()
        projs = load_projects()[load_projects()["Aktyor"] == actor]["Loyiha"].unique()
        if len(projs) == 0: return bot.send_message(message.chat.id, "❌ Sizga biriktirilgan loyihalar yo'q. Adminga murojaat qiling.")
        for p in projs: m.add(types.InlineKeyboardButton(p, callback_data=f"dub_{p}"))
        bot.send_message(message.chat.id, "✅ Fayl olindi! Loyihani tanlang:", reply_markup=m)

    @bot.callback_query_handler(func=lambda c: c.data.startswith("monsub_") or c.data.startswith("dub_"))
    def proc_sub(call):
        is_mon = call.data.startswith("monsub_")
        p = call.data.split("_")[1]
        (montajchi_cache if is_mon else user_submission_cache)[call.from_user.id]['project'] = p
        bot.register_next_step_handler(bot.send_message(call.message.chat.id, "🔢 Nechinchi qism? (Faqat raqam yozing)"), lambda m: fin_sub(m, is_mon))

    def fin_sub(message, is_mon):
        if not message.text or not message.text.isdigit():
            return bot.send_message(message.chat.id, "⚠️ Xato! Qism faqat raqamlarda yozilishi shart. Qaytadan urinib ko'ring.")
            
        cache = montajchi_cache if is_mon else user_submission_cache
        d = cache[message.from_user.id]
        actor = load_data().loc[load_data()["Telegram_ID"] == message.from_user.id, "Ism"].values[0]
        try:
            rate = int(load_projects()[(load_projects()["Loyiha"] == d['project']) & (load_projects()["Aktyor"] == actor)]["Narx"].values[0])
        except IndexError:
            return bot.send_message(message.chat.id, "❌ Ushbu loyiha bo'yicha sizning narxingiz (stavka) topilmadi.")
        
        df = load_data(); df.loc[df["Ism"] == actor, "Ishladi"] += rate; save_df(df, DB_FILE)
        
        c_main = f"💿 **YANGI ISH**\n🎬 {d['project']} ({message.text}-qism)\n👤 Muallif: {actor}\n💰 Smeta: {rate:,} so'm"
        if is_mon:
            for typ, msg in [("Video", d['vid']), ("Audio", d['aud'])]: bot.copy_message(CHANNEL_ID, message.chat.id, msg.message_id, caption=f"{c_main}\n\n🗂 Turi: {typ}")
        else:
            bot.copy_message(CHANNEL_ID, message.chat.id, d['msg'].message_id, caption=c_main)
            
        bot.send_message(message.chat.id, f"✅ Kanalga yuborildi! Balansga {rate:,} so'm yozildi."); del cache[message.from_user.id]
        
