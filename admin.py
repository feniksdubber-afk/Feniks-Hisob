import pandas as pd
from telebot import types
import random
from config import *
from database import *

payment_cache = {}
admin_reply_cache = {}

def register_admin_handlers(bot):
    
    # ==========================================
    # 📊 MOLIYA VA HISOBOTLAR
    # ==========================================
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

    # ==========================================
    # 💸 ISHCHILARGA PUL TO'LASH
    # ==========================================
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

    # ==========================================
    # 📝 SHAXSIY VAZIFA QO'SHISH (YANGI)
    # ==========================================
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

    # ==========================================
    # 💬 XODIM XATIGA JAVOB YAZISH (YANGI)
    # ==========================================
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

    # ==========================================
    # 👤 XODIM QO'SHISH VA O'CHIRISH
    # ==========================================
    @bot.message_handler(func=lambda m: m.text == "👤 Xodim Qo'shish" and m.from_user.id == ADMIN_ID)
    def add_emp_start(message):
        bot.register_next_step_handler(bot.send_message(message.chat.id, "Yangi xodimning ismini yozing:"), add_emp_role)

    def add_emp_role(message):
        name = message.text
        markup = types.InlineKeyboardMarkup(row_width=2)
        markup.add(types.InlineKeyboardButton("🎙 Aktyor", callback_data=f"addrole_{name}_Aktyor"),
                   types.InlineKeyboardButton("📝 Tarjimon", callback_data=f"addrole_{name}_Tarjimon"),
                   types.InlineKeyboardButton("🎧 Audio montajchi", callback_data=f"addrole_{name}_Audio montajchi"),
                   types.InlineKeyboardButton("✍️ Elon yozishchi", callback_data=f"addrole_{name}_Elon yozishchi"))
        bot.send_message(message.chat.id, f"{name} qaysi lavozimda ishlaydi?", reply_markup=markup)

    @bot.callback_query_handler(func=lambda call: call.data.startswith("addrole_"))
    def save_new_emp(call):
        parts = call.data.split("_")
        name = parts[1]; role = parts[2]; pin = str(random.randint(1000, 9999))
        df = load_data()
        new_row = pd.DataFrame({"Ism": [name], "Ishladi": [0], "To'landi": [0], "Telegram_ID": [0], "Parol": [pin], "Karta": ["Kiritilmagan"], "Lavozim": [role]})
        save_df(pd.concat([df, new_row], ignore_index=True), DB_FILE)
        bot.edit_message_text(f"✅ Yangi xodim qo'shildi!\n👤 Ism: {name}\n💼 Lavozim: {role}\n🔐 PIN: `{pin}`", call.message.chat.id, call.message.message_id)

    @bot.message_handler(func=lambda m: m.text == "👤 Xodimni O'chirish" and m.from_user.id == ADMIN_ID)
    def del_emp(message):
        markup = types.InlineKeyboardMarkup()
        for _, r in load_data().iterrows():
            if r["Lavozim"] != "Admin": markup.add(types.InlineKeyboardButton(f"❌ {r['Ism']}", callback_data=f"delemp_{r['Ism']}"))
        bot.send_message(message.chat.id, "Kimni o'chirmoqchisiz?", reply_markup=markup)

    @bot.callback_query_handler(func=lambda call: call.data.startswith("delemp_"))
    def del_emp_fin(call):
        n = call.data.split("_")[1]
        save_df(load_data()[load_data()["Ism"] != n], DB_FILE)
        save_df(load_projects()[load_projects()["Aktyor"] != n], PROJECTS_FILE)
        bot.edit_message_text(f"✅ {n} o'chirildi.", call.message.chat.id, call.message.message_id)

    # ==========================================
    # 📣 E'LON YUBORISH
    # ==========================================
    @bot.message_handler(func=lambda m: m.text == "📣 E'lon Yuborish" and m.from_user.id == ADMIN_ID)
    def broadcast_start(message):
        bot.register_next_step_handler(bot.send_message(message.chat.id, "📢 Barcha xodimlarga e'lon matni:\n*(Bekor qilish uchun /cancel)*"), broadcast_send)

    def broadcast_send(message):
        if message.text == '/cancel': return bot.send_message(message.chat.id, "❌ Bekor qilindi.")
        for uid in load_data()[load_data()["Telegram_ID"] != 0]["Telegram_ID"].unique():
            try: bot.send_message(uid, f"📢 **MUHIM E'LON**\n\n{message.text}")
            except: continue
        bot.send_message(message.chat.id, "✅ E'lon tarqatildi.")

    # ==========================================
    # 🎬 LOYIHALAR VA BOSHQA SOZLAMALAR
    # ==========================================
    @bot.message_handler(func=lambda m: m.text == "🎬 Loyihalar" and m.from_user.id == ADMIN_ID)
    def manage_projects_main(message):
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(types.InlineKeyboardButton("➕ Yangi Loyiha yaratish", callback_data="p_add"))
        for p in load_projects()["Loyiha"].unique(): markup.add(types.InlineKeyboardButton(f"⚙️ {p} (Tahrirlash)", callback_data=f"p_edit_{p}"))
        bot.send_message(message.chat.id, "📁 **Loyihalar Boshqaruvi:**", reply_markup=markup)

    @bot.callback_query_handler(func=lambda call: call.data == "p_add")
    def p_add_step1(call):
        bot.clear_step_handler_by_chat_id(call.message.chat.id)
        bot.register_next_step_handler(bot.send_message(call.message.chat.id, "Yangi loyiha nomini yozing:"), p_add_step2)

    def p_add_step2(message):
        p_name = message.text
        markup = types.InlineKeyboardMarkup(row_width=2)
        for a in load_data()["Ism"]:
            if a != "Feniks": markup.add(types.InlineKeyboardButton(a, callback_data=f"setrate_{p_name}_{a}"))
        markup.add(types.InlineKeyboardButton("✅ TUGATISH", callback_data="done"))
        bot.send_message(message.chat.id, f"'{p_name}' yaratildi. Qaysi xodimlarga narx belgilaymiz?", reply_markup=markup)

    @bot.callback_query_handler(func=lambda call: call.data.startswith("setrate_"))
    def set_r(c):
        bot.clear_step_handler_by_chat_id(c.message.chat.id)
        bot.register_next_step_handler(bot.send_message(c.message.chat.id, f"💰 **{c.data.split('_')[2]}** narxi:"), lambda m: (save_df(pd.concat([load_projects()[~((load_projects()["Loyiha"] == c.data.split('_')[1]) & (load_projects()["Aktyor"] == c.data.split('_')[2]))], pd.DataFrame({"Loyiha": [c.data.split('_')[1]], "Aktyor": [c.data.split('_')[2]], "Narx": [int(m.text)]})], ignore_index=True), PROJECTS_FILE), bot.send_message(m.chat.id, "✅ Saqlandi.")))

    @bot.callback_query_handler(func=lambda call: call.data == "done")
    def done_p(c): bot.delete_message(c.message.chat.id, c.message.message_id)

    @bot.callback_query_handler(func=lambda call: call.data.startswith("p_edit_"))
    def edit_proj_menu(call):
        p_name = call.data.split("_", 2)[2]
        markup = types.InlineKeyboardMarkup(row_width=2)
        markup.add(types.InlineKeyboardButton("✏️ Nomini o'zgartirish", callback_data=f"pren_{p_name}"), types.InlineKeyboardButton("🗑 O'chirish", callback_data=f"pdel_{p_name}"))
        markup.add(types.InlineKeyboardButton("➕ Xodim qo'shish", callback_data=f"paddact_{p_name}"), types.InlineKeyboardButton("➖ Xodim olib tashlash", callback_data=f"premact_{p_name}"))
        bot.edit_message_text(f"⚙️ **{p_name}** loyihasi sozlamalari:", call.message.chat.id, call.message.message_id, reply_markup=markup)

    @bot.callback_query_handler(func=lambda call: call.data.startswith("pren_"))
    def proj_rename(call):
        bot.clear_step_handler_by_chat_id(call.message.chat.id)
        bot.register_next_step_handler(bot.send_message(call.message.chat.id, "Yangi nomni yozing:"), lambda m: (save_df(load_projects().assign(Loyiha=lambda x: x['Loyiha'].replace(call.data.split('_', 1)[1], m.text)), PROJECTS_FILE), bot.send_message(m.chat.id, "✅ Nom o'zgardi.")))

    @bot.callback_query_handler(func=lambda call: call.data.startswith("pdel_"))
    def proj_delete(call):
        p_name = call.data.split("_", 1)[1]
        save_df(load_projects()[load_projects()["Loyiha"] != p_name], PROJECTS_FILE)
        bot.edit_message_text(f"🗑 '{p_name}' butunlay o'chirildi.", call.message.chat.id, call.message.message_id)

    @bot.callback_query_handler(func=lambda call: call.data.startswith("paddact_"))
    def proj_add_act(call):
        p_name = call.data.split("_", 1)[1]
        markup = types.InlineKeyboardMarkup(row_width=2)
        for a in load_data()["Ism"]:
            if a != "Feniks": markup.add(types.InlineKeyboardButton(a, callback_data=f"setrate_{p_name}_{a}"))
        bot.edit_message_text(f"Qaysi xodimni qo'shamiz?", call.message.chat.id, call.message.message_id, reply_markup=markup)

    @bot.callback_query_handler(func=lambda call: call.data.startswith("premact_"))
    def proj_rem_act(call):
        p_name = call.data.split("_", 1)[1]
        markup = types.InlineKeyboardMarkup(row_width=2)
        for a in load_projects()[load_projects()["Loyiha"] == p_name]["Aktyor"]: markup.add(types.InlineKeyboardButton(f"❌ {a}", callback_data=f"rmvact_{p_name}_{a}"))
        bot.edit_message_text("Kimni olib tashlaymiz?", call.message.chat.id, call.message.message_id, reply_markup=markup)

    @bot.callback_query_handler(func=lambda call: call.data.startswith("rmvact_"))
    def exec_rmv_act(call):
        parts = call.data.split("_", 2)
        pr_df = load_projects()
        save_df(pr_df[~((pr_df["Loyiha"] == parts[1]) & (pr_df["Aktyor"] == parts[2]))], PROJECTS_FILE)
        bot.edit_message_text(f"✅ {parts[2]} loyihadan olib tashlandi.", call.message.chat.id, call.message.message_id)

    # ==========================================
    # 🔤 TIZIM MATNLARI VA MENU BUILDER
    # ==========================================
    @bot.message_handler(func=lambda m: m.text in ["🔤 Tizim Matnlari", "🛠 Menu Builder"] and m.from_user.id == ADMIN_ID)
    def admin_extras(message):
        bot.clear_step_handler_by_chat_id(message.chat.id)
        if message.text == "🔤 Tizim Matnlari":
            markup = types.InlineKeyboardMarkup(row_width=1)
            names = {"moliya": "📊 Moliya", "parol": "🔑 Parollar", "ovoz": "📥 Material yuborish", "vazifa_yoq": "📋 Vazifa yo'q", "vazifa_bor": "📋 Vazifa bor", "start_admin": "🚀 Start (Admin)", "start_actor": "🚀 Start (Xodim)"}
            for key, val in names.items(): markup.add(types.InlineKeyboardButton(val, callback_data=f"edittext_{key}"))
            bot.send_message(message.chat.id, "🔤 **Matnni tanlang:**", reply_markup=markup)
        elif message.text == "🛠 Menu Builder":
            bot.send_message(message.chat.id, "🎛 **Menu Builder:**", reply_markup=types.InlineKeyboardMarkup().add(types.InlineKeyboardButton("➕ Yangi Tugma", callback_data="add_btn"), types.InlineKeyboardButton("🗑 O'chirish", callback_data="del_btn")))

    @bot.callback_query_handler(func=lambda call: call.data.startswith("edittext_"))
    def edit_text_step1(call):
        key = call.data.split("_")[1]
        bot.register_next_step_handler(bot.send_message(call.message.chat.id, f"📌 **Joriy matn:**\n_{get_text(key)}_\n\n✏️ **Yangi matnni yuboring:**"), lambda m: (save_df(load_texts().assign(Matn=lambda x: [m.text if k == key else v for k, v in zip(x['Key'], x['Matn'])]), TEXTS_FILE), bot.send_message(m.chat.id, "✅ Matn yangilandi!")))

    @bot.callback_query_handler(func=lambda call: call.data in ["add_btn", "del_btn"])
    def admin_extra_calls(call):
        bot.clear_step_handler_by_chat_id(call.message.chat.id)
        if call.data == "add_btn": bot.register_next_step_handler(bot.send_message(call.message.chat.id, "Tugma nomini yozing:"), lambda m: bot.register_next_step_handler(bot.send_message(m.chat.id, "Matn yozing:"), lambda msg: (save_df(pd.concat([load_custom_menu(), pd.DataFrame({"Tugma_Nomi": [m.text], "Xabar": [msg.text]})], ignore_index=True), MENU_FILE), bot.send_message(msg.chat.id, f"✅ '{m.text}' qo'shildi! /start bosing."))))
        elif call.data == "del_btn":
            df = load_custom_menu()
            if df.empty: return bot.send_message(call.message.chat.id, "Tugmalar yo'q.")
            markup = types.InlineKeyboardMarkup()
            for btn in df["Tugma_Nomi"]: markup.add(types.InlineKeyboardButton(f"❌ {btn}", callback_data=f"delbtn_{btn}"))
            bot.send_message(call.message.chat.id, "O'chiramiz:", reply_markup=markup)

    @bot.callback_query_handler(func=lambda call: call.data.startswith("delbtn_"))
    def del_button_save(call):
        btn_name = call.data.split("_", 1)[1]
        save_df(load_custom_menu()[load_custom_menu()["Tugma_Nomi"] != btn_name], MENU_FILE)
        bot.edit_message_text(f"✅ O'chirildi. /start bosing.", call.message.chat.id, call.message.message_id)

