import telebot
from telebot import types
import pandas as pd
import os
import threading
import random
from flask import Flask

# ==========================================
# ⚙️ 1-BLOK: ASOSIY SOZLAMALAR VA BAZA DVIGATELI
# ==========================================
TOKEN = '6844735110:AAE1y58TDn1Kah9SewVx_IFTHBXNZOupJ4w'
ADMIN_ID = 6761276533
CHANNEL_ID = -1003634886616 

bot = telebot.TeleBot(TOKEN, parse_mode="Markdown")
app = Flask(__name__)

DB_FILE = "feniks_v12.csv"
PROJECTS_FILE = "projects_v12.csv"
MENU_FILE = "custom_menu_v12.csv"
TASKS_FILE = "tasks_v12.csv"
TEXTS_FILE = "texts_v12.csv" 

STATIC_BUTTONS = ["📊 Moliya", "💸 Ishchilarga pul tashlash", "🎬 Loyihalar", "👤 Xodim Qo'shish", "👤 Xodimni O'chirish", "📣 E'lon Yuborish", "🔑 Parollar", "📁 Excel", "📝 Vazifa Qo'shish", "🛠 Menu Builder", "🔤 Tizim Matnlari", "🎙 Ovoz/Material topshirish", "💰 Mening Hisobim", "📋 Faol Vazifalar", "🔐 Parolni o'zgartirish", "🎧 Tayyor Material Yuborish", "✍️ Tayyor Elonni yuborish"]

# --- KUCHAYTIRILGAN BAZA YUKLASH (Ma'lumotlar o'chmasligi uchun) ---
def load_data():
    if not os.path.exists(DB_FILE):
        if os.path.exists("feniks_v11.csv"):
            df = pd.read_csv("feniks_v11.csv")
            if "Karta" not in df.columns: df["Karta"] = "Kiritilmagan"
            if "Lavozim" not in df.columns: df["Lavozim"] = "Aktyor"
            df.loc[df["Ism"] == "Feniks", "Lavozim"] = "Admin"
            df.loc[df["Ism"] == "Tarjimon", "Lavozim"] = "Tarjimon"
            df.to_csv(DB_FILE, index=False)
        else:
            actors = ["Zoom", "Umarbek", "AMIN", "Bexruz", "Komron", "Shabnam", "Kamilla", "Tarjimon", "Feniks"]
            df = pd.DataFrame({
                "Ism": actors, "Ishladi": [0]*9, "To'landi": [0]*9,
                "Telegram_ID": [0]*9, "Parol": [str(random.randint(1000, 9999)) for _ in range(9)],
                "Karta": ["Kiritilmagan"]*9, "Lavozim": ["Aktyor"]*9
            })
            df.loc[df["Ism"] == "Feniks", "Telegram_ID"] = ADMIN_ID
            df.loc[df["Ism"] == "Feniks", "Lavozim"] = "Admin"
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
            "moliya": "📊 **FENIKS STUDIO UMUMIY HISOBOTI**",
            "parol": "🔑 **Xodimlar PIN-kodlari:**",
            "ovoz": "📥 **Material topshirish qo'llanmasi:**\n\nFayl yuboring, bot avtomatik loyihani so'raydi!",
            "vazifa_yoq": "🎉 Hozircha yangi vazifalar yo'q. Dam oling!",
            "vazifa_bor": "📌 **FENIKS STUDIO VAZIFALARI:**",
            "start_admin": "👑 Xush kelibsiz, Rejissyor!",
            "start_actor": "🎧 Salom! Ishga tayyormisiz?"
        }
        df = pd.DataFrame(list(defaults.items()), columns=["Key", "Matn"])
        df.to_csv(TEXTS_FILE, index=False)
    return pd.read_csv(TEXTS_FILE)

def get_text(key):
    try: return load_texts().loc[load_texts()["Key"] == key, "Matn"].values[0]
    except: return "Matn topilmadi"

def save_df(df, file):
    df.to_csv(file, index=False)
    # ==========================================
# 🎛 2-BLOK: DINAMIK MENYULAR VA AKKAUNT
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
        markup.add("📋 Faol Vazifalar", "🔐 Parolni o'zgartirish")
    elif lavozim == "Elon yozishchi":
        markup.add("✍️ Tayyor Elonni yuborish", "💰 Mening Hisobim")
        markup.add("📋 Faol Vazifalar", "🔐 Parolni o'zgartirish")
    else:
        markup.add("🎙 Ovoz/Material topshirish", "💰 Mening Hisobim")
        markup.add("📋 Faol Vazifalar", "🔐 Parolni o'zgartirish")
        
    for btn in custom_df["Tugma_Nomi"]: markup.add(btn)
    return markup

@bot.message_handler(commands=['start'])
def start(message):
    df = load_data()
    user_id = message.from_user.id
    bot.clear_step_handler_by_chat_id(message.chat.id) # Barcha eski qadamlarni tozalash
    head = "🎬 **FENIKS STUDIO | ELITE v12.0**\n" + "━" * 25 + "\n"
    
    if user_id in df["Telegram_ID"].values:
        row = df[df["Telegram_ID"] == user_id].iloc[0]
        if row["Lavozim"] == "Admin": bot.send_message(message.chat.id, head + get_text("start_admin"), reply_markup=main_menu(user_id))
        else: bot.send_message(message.chat.id, head + f"👤 **{row['Ism']}** ({row['Lavozim']}),\n\n" + get_text("start_actor"), reply_markup=main_menu(user_id))
    else:
        bot.send_message(message.chat.id, head + "🔐 Tizimga kirish uchun 4 xonali PIN-kodni yuboring:")

@bot.message_handler(commands=['reset'])
def reset_account(message):
    df = load_data()
    if message.from_user.id in df["Telegram_ID"].values:
        df.loc[df["Telegram_ID"] == message.from_user.id, "Telegram_ID"] = 0
        save_df(df, DB_FILE)
        bot.send_message(message.chat.id, "🚪 Akkauntdan chiqdingiz. Qaytadan kirish uchun /start bosing.", reply_markup=types.ReplyKeyboardRemove())

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

# --- PAROL O'ZGARTIRISH (To'liq himoyalangan) ---
change_pass_cache = []

@bot.message_handler(func=lambda m: m.text == "🔐 Parolni o'zgartirish")
def change_pass_start(message):
    df = load_data()
    if message.from_user.id not in df["Telegram_ID"].values: return
    if message.from_user.id not in change_pass_cache: change_pass_cache.append(message.from_user.id)
    bot.send_message(message.chat.id, "✏️ **Yangi 4 xonali PIN-kod o'ylab toping va yozib yuboring:**\n*(Faqat raqamlardan iborat bo'lsin)*")

@bot.message_handler(func=lambda m: m.from_user.id in change_pass_cache)
def change_pass_save(message):
    if message.text.isdigit() and len(message.text) == 4:
        df = load_data()
        df.loc[df["Telegram_ID"] == message.from_user.id, "Parol"] = message.text
        save_df(df, DB_FILE)
        bot.send_message(message.chat.id, f"✅ Parolingiz muvaffaqiyatli o'zgardi! Yangi parolingiz: `{message.text}`")
        change_pass_cache.remove(message.from_user.id)
    else:
        bot.send_message(message.chat.id, "⚠️ Xato! Parol aynan 4 ta raqamdan iborat bo'lishi shart. Boshidan urining.")
        change_pass_cache.remove(message.from_user.id)
        # ==========================================
# 👑 3-BLOK: XODIMLAR VA E'LONLAR BOSHQRUVI
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
def delete_emp_start(message):
    markup = types.InlineKeyboardMarkup(row_width=2)
    added = False
    for _, r in load_data().iterrows():
        if r["Lavozim"] != "Admin":
            markup.add(types.InlineKeyboardButton(f"❌ {r['Ism']}", callback_data=f"delemp_{r['Ism']}")); added = True
    if added: bot.send_message(message.chat.id, "🗑 Qaysi xodimni bazadan butunlay o'chirib tashlamoqchisiz?", reply_markup=markup)
    else: bot.send_message(message.chat.id, "O'chirish uchun xodimlar topilmadi.")

@bot.callback_query_handler(func=lambda call: call.data.startswith("delemp_"))
def delete_emp_confirm(call):
    name = call.data.split("_")[1]
    save_df(load_data()[load_data()["Ism"] != name], DB_FILE)
    save_df(load_projects()[load_projects()["Aktyor"] != name], PROJECTS_FILE)
    bot.edit_message_text(f"✅ **{name}** va unga tegishli barcha ma'lumotlar bazadan o'chirildi.", call.message.chat.id, call.message.message_id)

@bot.message_handler(func=lambda m: m.text == "📣 E'lon Yuborish" and m.from_user.id == ADMIN_ID)
def broadcast_start(message):
    bot.register_next_step_handler(bot.send_message(message.chat.id, "📣 Barcha xodimlarga yuboriladigan e'lon matnini yozing:\n*(Bekor qilish uchun /cancel yozing)*"), broadcast_send)

def broadcast_send(message):
    if message.text == '/cancel': return bot.send_message(message.chat.id, "❌ E'lon yuborish bekor qilindi.")
    users = load_data()[load_data()["Telegram_ID"] != 0]["Telegram_ID"].unique()
    count = 0
    for user_id in users:
        try: bot.send_message(user_id, f"📢 **FENIKS STUDIO - MUHIM E'LON**\n━━━━━━━━━━━━━━━━━━━━\n\n{message.text}\n\n━━━━━━━━━━━━━━━━━━━━\n👤 *Admin tomonidan yuborildi*"); count += 1
        except: continue
    bot.send_message(message.chat.id, f"✅ E'lon muvaffaqiyatli yuborildi! Jami: {count} ta xodimga.")
    # ==========================================
# 💰 4-BLOK: MOLIYA VA LOYIHALAR (ADMIN)
# ==========================================
payment_cache = {}

@bot.message_handler(func=lambda m: m.text == "💸 Ishchilarga pul tashlash" and m.from_user.id == ADMIN_ID)
def pay_init(message):
    markup = types.InlineKeyboardMarkup(row_width=2)
    added = False
    for _, r in load_data().iterrows():
        if r["Lavozim"] != "Admin":
            b = int(r["Ishladi"]) - int(r["To'landi"])
            markup.add(types.InlineKeyboardButton(f"{r['Ism']} ({b:,} so'm)", callback_data=f"payto_{r['Ism']}"))
            added = True
    if added: bot.send_message(message.chat.id, "💳 Pul o'tkaziladigan xodimni tanlang:", reply_markup=markup)
    else: bot.send_message(message.chat.id, "❌ Xodimlar yo'q.")

@bot.callback_query_handler(func=lambda call: call.data.startswith("payto_"))
def pay_step1(call):
    actor = call.data.split("_")[1]
    df = load_data()
    row = df[df["Ism"] == actor].iloc[0]
    balans = int(row["Ishladi"]) - int(row["To'landi"])
    payment_cache[call.from_user.id] = {'actor': actor, 'karta': row["Karta"], 'balans': balans}
    
    bot.clear_step_handler_by_chat_id(call.message.chat.id)
    msg = bot.send_message(call.message.chat.id, f"👤 **{actor}**\n💳 Karta: `{row['Karta']}`\n💰 Balans: {balans:,} so'm\n\nQancha pul to'laysiz? (Faqat raqam yozing):")
    bot.register_next_step_handler(msg, pay_step2)

def pay_step2(message):
    if not message.text.isdigit():
        return bot.send_message(message.chat.id, "⚠️ Faqat raqam kiriting. Boshidan boshlang.")
    payment_cache[message.from_user.id]['summa'] = int(message.text)
    msg = bot.send_message(message.chat.id, "📝 Bu to'lov qaysi loyihalar/qismlar uchun? (Masalan: Sin Mu 10-11 qismlar):")
    bot.register_next_step_handler(msg, pay_step3)

def pay_step3(message):
    payment_cache[message.from_user.id]['sabab'] = message.text
    msg = bot.send_message(message.chat.id, "📸 Iltimos, to'lov chekini (rasmini) yuboring:")
    bot.register_next_step_handler(msg, pay_step4)

def pay_step4(message):
    if message.content_type != 'photo': return bot.send_message(message.chat.id, "⚠️ Bu rasm emas! To'lov bekor qilindi.")
    data = payment_cache[message.from_user.id]
    df = load_data()
    df.loc[df["Ism"] == data['actor'], "To'landi"] += data['summa']
    save_df(df, DB_FILE)
    
    yangi_balans = data['balans'] - data['summa']
    bot.send_message(message.chat.id, f"✅ To'lov saqlandi!\n{data['actor']}ning qolgan balansi: {yangi_balans:,} so'm.")
    
    actor_id = df.loc[df["Ism"] == data['actor'], "Telegram_ID"].values[0]
    if actor_id != 0:
        caption = f"🎉 **Tabriklaymiz! To'lov qabul qildingiz!**\n\n💰 **Summa:** {data['summa']:,} so'm\n🎬 **Loyiha:** {data['sabab']}\n💳 **Karta:** {data['karta']}\n\n💼 **Joriy balansingiz:** {yangi_balans:,} so'm"
        try: bot.send_photo(actor_id, message.photo[-1].file_id, caption=caption)
        except: pass
    del payment_cache[message.from_user.id]

# --- QOLGAN ADMIN FUNKSIYALARI (Hisobotlar, Loyihalar va Matnlar) ---
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

@bot.message_handler(func=lambda m: m.text in ["🔤 Tizim Matnlari", "🛠 Menu Builder", "📝 Vazifa Qo'shish"] and m.from_user.id == ADMIN_ID)
def admin_extras(message):
    bot.clear_step_handler_by_chat_id(message.chat.id)
    if message.text == "🔤 Tizim Matnlari":
        markup = types.InlineKeyboardMarkup(row_width=1)
        names = {"moliya": "📊 Moliya", "parol": "🔑 Parollar", "ovoz": "📥 Material yuborish", "vazifa_yoq": "📋 Vazifa yo'q", "vazifa_bor": "📋 Vazifa bor", "start_admin": "🚀 Start (Admin)", "start_actor": "🚀 Start (Xodim)"}
        for key, val in names.items(): markup.add(types.InlineKeyboardButton(val, callback_data=f"edittext_{key}"))
        bot.send_message(message.chat.id, "🔤 **Matnni tanlang:**", reply_markup=markup)
    elif message.text == "🛠 Menu Builder":
        bot.send_message(message.chat.id, "🎛 **Menu Builder:**", reply_markup=types.InlineKeyboardMarkup().add(types.InlineKeyboardButton("➕ Yangi Tugma", callback_data="add_btn"), types.InlineKeyboardButton("🗑 O'chirish", callback_data="del_btn")))
    elif message.text == "📝 Vazifa Qo'shish":
        bot.register_next_step_handler(bot.send_message(message.chat.id, "Vazifani yozing:", reply_markup=types.InlineKeyboardMarkup().add(types.InlineKeyboardButton("🗑 Tozalash", callback_data="clear_tasks"))), lambda m: (save_df(pd.concat([load_tasks(), pd.DataFrame({"ID": [len(load_tasks())+1], "Matn": [m.text]})], ignore_index=True), TASKS_FILE), bot.send_message(m.chat.id, "✅ Vazifa qo'shildi!")) if m.text else None)

@bot.callback_query_handler(func=lambda call: call.data.startswith("edittext_"))
def edit_text_step1(call):
    key = call.data.split("_")[1]
    bot.register_next_step_handler(bot.send_message(call.message.chat.id, f"📌 **Joriy matn:**\n_{get_text(key)}_\n\n✏️ **Yangi matnni yuboring:**"), lambda m: (save_df(load_texts().assign(Matn=lambda x: [m.text if k == key else v for k, v in zip(x['Key'], x['Matn'])]), TEXTS_FILE), bot.send_message(m.chat.id, "✅ Matn yangilandi!")))

@bot.callback_query_handler(func=lambda call: call.data in ["add_btn", "del_btn", "clear_tasks"])
def admin_extra_calls(call):
    bot.clear_step_handler_by_chat_id(call.message.chat.id)
    if call.data == "add_btn": bot.register_next_step_handler(bot.send_message(call.message.chat.id, "Tugma nomini yozing:"), lambda m: bot.register_next_step_handler(bot.send_message(m.chat.id, "Matn yozing:"), lambda msg: (save_df(pd.concat([load_custom_menu(), pd.DataFrame({"Tugma_Nomi": [m.text], "Xabar": [msg.text]})], ignore_index=True), MENU_FILE), bot.send_message(msg.chat.id, f"✅ '{m.text}' qo'shildi! /start bosing."))))
    elif call.data == "del_btn":
        df = load_custom_menu()
        if df.empty: return bot.send_message(call.message.chat.id, "Tugmalar yo'q.")
        markup = types.InlineKeyboardMarkup()
        for btn in df["Tugma_Nomi"]: markup.add(types.InlineKeyboardButton(f"❌ {btn}", callback_data=f"delbtn_{btn}"))
        bot.send_message(call.message.chat.id, "O'chiramiz:", reply_markup=markup)
    elif call.data == "clear_tasks":
        save_df(pd.DataFrame(columns=["ID", "Matn"]), TASKS_FILE); bot.edit_message_text("✅ O'chirildi.", call.message.chat.id, call.message.message_id)

@bot.callback_query_handler(func=lambda call: call.data.startswith("delbtn_"))
def del_button_save(call):
    btn_name = call.data.split("_", 1)[1]
    save_df(load_custom_menu()[load_custom_menu()["Tugma_Nomi"] != btn_name], MENU_FILE)
    bot.edit_message_text(f"✅ O'chirildi. /start bosing.", call.message.chat.id, call.message.message_id)
        # ==========================================
# 💳 5-BLOK: XODIMLAR PANELI VA BALANS
# ==========================================
@bot.message_handler(func=lambda m: m.text == "💰 Mening Hisobim")
def my_acc(message):
    r = load_data()[load_data()["Telegram_ID"] == message.from_user.id].iloc[0]
    m = types.InlineKeyboardMarkup().add(types.InlineKeyboardButton("💳 Karta kiritish/o'zgartirish", callback_data="edit_card"), types.InlineKeyboardButton("🗑 Tozalash (0 qilish)", callback_data="clr_bal"))
    bot.send_message(message.chat.id, f"👤 **{r['Ism']}** ({r['Lavozim']})\n💰 Balans: {int(r['Ishladi'])-int(r['To\'landi']):,}\n💳 Karta: `{r['Karta']}`", reply_markup=m)

@bot.callback_query_handler(func=lambda call: call.data == "edit_card")
def ed_card(call): 
    bot.clear_step_handler_by_chat_id(call.message.chat.id)
    bot.register_next_step_handler(bot.send_message(call.message.chat.id, "💳 Yangi karta raqam yozing:"), ed_card_save)

def ed_card_save(m): 
    (load_data().assign(Karta=lambda x: [m.text if tid == m.from_user.id else k for tid, k in zip(x['Telegram_ID'], x['Karta'])]).pipe(save_df, DB_FILE), bot.send_message(m.chat.id, f"✅ Karta saqlandi: `{m.text}`"))

@bot.callback_query_handler(func=lambda call: call.data == "clr_bal")
def clr_bal(call): 
    (load_data().assign(Ishladi=lambda x: [0 if tid == call.from_user.id else i for tid, i in zip(x['Telegram_ID'], x['Ishladi'])], To_landi=lambda x: [0 if tid == call.from_user.id else t for tid, t in zip(x['Telegram_ID'], x['To_landi'])]).pipe(save_df, DB_FILE), bot.edit_message_text("✅ Balans nollashtirildi.", call.message.chat.id, call.message.message_id))

@bot.message_handler(func=lambda m: m.text == "📋 Faol Vazifalar")
def show_tasks(message):
    tasks_df = load_tasks()
    if tasks_df.empty: bot.send_message(message.chat.id, get_text("vazifa_yoq"))
    else: bot.send_message(message.chat.id, get_text("vazifa_bor") + "\n\n" + "".join([f"🔸 {r['Matn']}\n\n" for _, r in tasks_df.iterrows()]))

@bot.message_handler(func=lambda m: m.text in ["🎙 Ovoz/Material topshirish", "✍️ Tayyor Elonni yuborish"])
def show_guides(message):
    if message.text == "🎙 Ovoz/Material topshirish": bot.send_message(message.chat.id, get_text("ovoz"))
    elif message.text == "✍️ Tayyor Elonni yuborish": bot.send_message(message.chat.id, "✍️ Iltimos, kanalga yuborilishi kerak bo'lgan tayyor matnni shu yerga tashlang.")
                           # ==========================================
# 🎧 6-BLOK: UNIVERSAL QABUL QILGICH (ZOOMCHIK LOGIKASI)
# ==========================================
montajchi_cache = {} # Video va Audio fayllarni ketma-ket ushlab turish uchun

@bot.message_handler(func=lambda m: m.text == "🎧 Tayyor Material Yuborish")
def mon_start(message):
    df = load_data()
    if message.from_user.id not in df["Telegram_ID"].values: return
    
    # Montajchi jarayonni boshlaydi
    montajchi_cache[message.from_user.id] = {'step': 'video', 'video_msg': None, 'audio_msg': None}
    bot.send_message(message.chat.id, "🎧 **Montajchi paneli (1/2):**\n\nIltimos, avval **VIDEO** faylni yuboring:")

def is_valid_submission(message):
    if message.content_type in ['voice', 'audio', 'document', 'video']: return True
    if message.content_type == 'text' and not message.text.startswith('/') and message.text not in STATIC_BUTTONS: 
        custom_btns = load_custom_menu()["Tugma_Nomi"].tolist()
        if message.text not in custom_btns: return True
    return False

user_submission_cache = {}

@bot.message_handler(func=is_valid_submission, content_types=['voice', 'audio', 'document', 'video', 'text'])
def handle_all_submissions(message):
    df = load_data()
    if message.from_user.id not in df["Telegram_ID"].values: return
    row = df.loc[df["Telegram_ID"] == message.from_user.id].iloc[0]
    actor = row["Ism"]; lavozim = row["Lavozim"]
    
    # 1. ELON YOZISHCHI FILTRI
    if lavozim == "Elon yozishchi" and message.content_type == 'text':
        cap = f"✍️ **YANGI E'LON / POST**\n━━━━━━━━━━━━━━━━━━━━\n👤 **Muallif:** {actor}\n━━━━━━━━━━━━━━━━━━━━"
        bot.send_message(CHANNEL_ID, f"{cap}\n\n{message.text}")
        bot.send_message(message.chat.id, "✅ E'lon matni kanalga muvaffaqiyatli yuborildi! Rahmat!")
        return

    # 2. ZOOMCHIK (AUDIO MONTAJCHI) FILTRI - Ikkita fayl (Video + Audio)
    if lavozim == "Audio montajchi" and message.from_user.id in montajchi_cache:
        state = montajchi_cache[message.from_user.id]
        
        if state['step'] == 'video':
            if message.content_type not in ['video', 'document']:
                return bot.send_message(message.chat.id, "⚠️ Iltimos, avval tayyor **VIDEO** faylni (yoki videoli hujjatni) yuboring.")
            
            # Videoni ushladik, endi audioni so'raymiz
            montajchi_cache[message.from_user.id]['video_msg'] = message
            montajchi_cache[message.from_user.id]['step'] = 'audio'
            bot.send_message(message.chat.id, "✅ Video qabul qilindi.\n\n🎧 **Montajchi paneli (2/2):**\nEndi shu videoning **AUDIO (Orqafonsiz)** faylini yuboring:")
            return
            
        elif state['step'] == 'audio':
            if message.content_type not in ['audio', 'voice', 'document']:
                return bot.send_message(message.chat.id, "⚠️ Iltimos, faqatgina **AUDIO** (yoki orqafonsiz hujjat) faylini yuboring.")
            
            # Audioni ham ushladik, endi loyihani tanlashga o'tamiz
            montajchi_cache[message.from_user.id]['audio_msg'] = message
            my_projects = load_projects()[load_projects()["Aktyor"] == actor]["Loyiha"].unique()
            
            if len(my_projects) == 0:
                bot.send_message(message.chat.id, "❌ Sizga stavka belgilanmagan yoki loyihaga ulanmagansiz.")
                del montajchi_cache[message.from_user.id]
                return
                
            markup = types.InlineKeyboardMarkup(row_width=2)
            for p in my_projects: markup.add(types.InlineKeyboardButton(p, callback_data=f"monsub_{p}"))
            bot.send_message(message.chat.id, "🎬 **Ajoyib! Ikkala fayl (Video + Audio) qabul qilindi.**\n\nBu mehnatingiz qaysi loyiha uchun qilingan?", reply_markup=markup)
            return

    # 3. ODDIY AKTYOR/TARJIMON FILTRI
    user_submission_cache[message.from_user.id] = {'msg': message, 'actor': actor}
    my_projects = load_projects()[load_projects()["Aktyor"] == actor]["Loyiha"].unique()
    
    if len(my_projects) == 0: 
        return bot.send_message(message.chat.id, "❌ Fayl ushlandi, lekin sizga stavka belgilanmagan.")
        
    markup = types.InlineKeyboardMarkup(row_width=2)
    for p in my_projects: markup.add(types.InlineKeyboardButton(p, callback_data=f"dub_{p}"))
    bot.send_message(message.chat.id, f"✅ Fayl tizimga qabul qilindi!\n🎤 Qaysi loyiha uchun yubordingiz?", reply_markup=markup)

# --- ZOOMCHIK TUGATISH QISMI ---
@bot.callback_query_handler(func=lambda call: call.data.startswith("monsub_"))
def process_montaj_step(call):
    p = call.data.split("_")[1]
    montajchi_cache[call.from_user.id]['project'] = p
    bot.clear_step_handler_by_chat_id(call.message.chat.id)
    bot.edit_message_text(f"🔢 '{p}' loyihasining nechinchi qismi?", call.message.chat.id, call.message.message_id)
    bot.register_next_step_handler(call.message, final_montaj_process)

def final_montaj_process(message):
    try:
        data = montajchi_cache[message.from_user.id]
        df = load_data()
        actor = df.loc[df["Telegram_ID"] == message.from_user.id, "Ism"].values[0]
        pr_df = load_projects()
        rate = int(pr_df[(pr_df["Loyiha"] == data['project']) & (pr_df["Aktyor"] == actor)]["Narx"].values[0])
        
        # Pulni yozish (Ikkala fayl uchun faqat 1 ta stavka)
        df.loc[df["Ism"] == actor, "Ishladi"] += rate
        save_df(df, DB_FILE)
        
        cap_main = f"💿 **YANGI MONTAJ (VIDEO+AUDIO)**\n━━━━━━━━━━━━━━━━━━━━\n🎬 **Loyiha:** {data['project']}\n🔢 **Qism:** {message.text}\n👤 **Muallif:** {actor}\n💰 **Smeta:** {rate:,} so'm yozildi\n━━━━━━━━━━━━━━━━━━━━\n#{data['project'].replace(' ', '')}"
        
        # Ikkala faylni ham kanalga tashlash
        send_to_channel(data['video_msg'], f"{cap_main}\n\n📹 **Turi:** Tayyor Video")
        send_to_channel(data['audio_msg'], f"{cap_main}\n\n🎵 **Turi:** Tayyor Audio (Orqafonsiz)")
        
        bot.send_message(message.chat.id, f"✅ Har ikkala faylingiz ham kanalga muvaffaqiyatli yuborildi! Hisobingizga {rate:,} so'm qo'shildi. Mehnatingiz uchun Rahmat!")
        del montajchi_cache[message.from_user.id]
    except Exception as e: 
        bot.send_message(message.chat.id, "⚠️ Xatolik yuz berdi. Iltimos qaytadan urining.")

# --- AKTYOR TUGATISH QISMI ---
@bot.callback_query_handler(func=lambda call: call.data.startswith("dub_"))
def process_submission_step2(call):
    p = call.data.split("_")[1]
    user_submission_cache[call.from_user.id]['project'] = p
    bot.clear_step_handler_by_chat_id(call.message.chat.id)
    bot.edit_message_text(f"🔢 '{p}' loyihasining nechinchi qismi?", call.message.chat.id, call.message.message_id)
    bot.register_next_step_handler(call.message, final_submission_process)

def final_submission_process(message):
    try:
        data = user_submission_cache[message.from_user.id]
        pr_df = load_projects()
        rate = int(pr_df[(pr_df["Loyiha"] == data['project']) & (pr_df["Aktyor"] == data['actor'])]["Narx"].values[0])
        
        df = load_data()
        df.loc[df["Ism"] == data['actor'], "Ishladi"] += rate
        save_df(df, DB_FILE)
        
        cap = f"📥 **YANGI MATERIAL**\n━━━━━━━━━━━━━━━━━━━━\n🎬 **Loyiha:** {data['project']}\n👤 **Muallif:** {data['actor']}\n🔢 **Qism:** {message.text}\n💰 **Smeta:** {rate:,} so'm yozildi\n━━━━━━━━━━━━━━━━━━━━\n#{data['project'].replace(' ', '')}"
        
        send_to_channel(data['msg'], cap)
        bot.send_message(message.chat.id, f"✅ Barchasi muvaffaqiyatli kanalga yuborildi! Hisobingizga {rate:,} so'm qo'shildi.")
        del user_submission_cache[message.from_user.id]
    except Exception as e: 
        bot.send_message(message.chat.id, "⚠️ Xatolik yuz berdi. Qaytadan urinib ko'ring.")

def send_to_channel(msg_obj, caption):
    if msg_obj.content_type == 'voice': bot.send_voice(CHANNEL_ID, msg_obj.voice.file_id, caption=caption)
    elif msg_obj.content_type == 'audio': bot.send_audio(CHANNEL_ID, msg_obj.audio.file_id, caption=caption)
    elif msg_obj.content_type == 'document': bot.send_document(CHANNEL_ID, msg_obj.document.file_id, caption=caption)
    elif msg_obj.content_type == 'video': bot.send_video(CHANNEL_ID, msg_obj.video.file_id, caption=caption)
    elif msg_obj.content_type == 'text': bot.send_message(CHANNEL_ID, f"{caption}\n\n📝 **Yuborilgan Matn/Tarjima:**\n\n{msg_obj.text}")

# ==========================================
# 🧲 DINAMIK TUGMALAR VA SERVERNI YOQISH
# ==========================================
@bot.message_handler(func=lambda m: True)
def handle_custom_buttons(message):
    custom_df = load_custom_menu()
    if message.text in custom_df["Tugma_Nomi"].values:
        bot.send_message(message.chat.id, custom_df.loc[custom_df["Tugma_Nomi"] == message.text, "Xabar"].values[0])

@app.route('/')
def home(): return "FeniksStudio Elite v12.0 FINAL is Online!"

if __name__ == "__main__":
    bot.remove_webhook()
    threading.Thread(target=lambda: bot.infinity_polling(skip_pending=True)).start()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
