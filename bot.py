import telebot
from telebot import types
import sqlite3
import hashlib
import threading
import os
import time
from http.server import BaseHTTPRequestHandler, HTTPServer

# ==========================================
# 1. KONFIGURATSIYA VA SETUP
# ==========================================
TOKEN = os.environ.get('BOT_TOKEN', 'BU_YERGA_TOKEN_YOZILMAYDI')
ADMIN_GROUP_ID = int(os.environ.get('ADMIN_GROUP_ID', -100123456789)) # Guruh ID sini yozing

# Railway/Render Volume uchun yo'l
DB_DIR = "/app/data"
if not os.path.exists(DB_DIR) and os.environ.get('RAILWAY_ENVIRONMENT'):
    os.makedirs(DB_DIR, exist_ok=True)
DB_PATH = os.path.join(DB_DIR, "feniks_studio.db") if os.environ.get('RAILWAY_ENVIRONMENT') else "feniks_studio.db"

bot = telebot.TeleBot(TOKEN, parse_mode='HTML')
db_lock = threading.Lock()

# Foydalanuvchi holatlarini saqlash (State Management)
user_states = {} 

# ==========================================
# 2. XAVFSIZLIK VA BAZA FUNKSIYALARI
# ==========================================
def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def init_db():
    with db_lock:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Jadvallarni yaratish
        cursor.execute('''CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            telegram_id INTEGER UNIQUE,
            name TEXT,
            login TEXT UNIQUE,
            password_hash TEXT,
            phone TEXT,
            card_number TEXT,
            balance INTEGER DEFAULT 0,
            role TEXT DEFAULT 'user'
        )''')
        cursor.execute('''CREATE TABLE IF NOT EXISTS active_logins (
            telegram_id INTEGER PRIMARY KEY,
            user_id INTEGER,
            FOREIGN KEY(user_id) REFERENCES users(id)
        )''')
        cursor.execute('''CREATE TABLE IF NOT EXISTS projects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            price INTEGER DEFAULT 0,
            topic_id INTEGER
        )''')
        cursor.execute('''CREATE TABLE IF NOT EXISTS user_projects (
            user_id INTEGER,
            project_id INTEGER,
            price INTEGER DEFAULT 0,
            FOREIGN KEY(user_id) REFERENCES users(id),
            FOREIGN KEY(project_id) REFERENCES projects(id)
        )''')
        
        # Asosiy Adminni va Dastlabki loyihalarni yaratish
        cursor.execute("SELECT * FROM users WHERE role = 'admin'")
        if not cursor.fetchone():
            cursor.execute("INSERT INTO users (name, login, password_hash, role) VALUES (?,?,?,?)",
                           ("Rejissyor", "admin", hash_password("admin777"), "admin"))
            
            # Dastlabki loyihalar (Baza bo'sh bo'lmasligi uchun)
            default_projects = [("Gravity Falls (2-mavsum)", 50000), ("Hoppers", 60000), ("Elio", 55000)]
            for p_name, p_price in default_projects:
                cursor.execute("INSERT INTO projects (name, price) VALUES (?,?)", (p_name, p_price))
                
        conn.commit()
        conn.close()

init_db()

def get_db():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    return conn, conn.cursor()

def get_logged_user(tg_id):
    conn, cur = get_db()
    cur.execute('''SELECT u.* FROM users u 
                   JOIN active_logins al ON u.id = al.user_id 
                   WHERE al.telegram_id = ?''', (tg_id,))
    user = cur.fetchone()
    conn.close()
    return user

def safe_delete(chat_id, message_id):
    try: bot.delete_message(chat_id, message_id)
    except: pass

# ==========================================
# 3. KLAVIATURALAR (UI/UX)
# ==========================================
def main_menu_kb(role='user'):
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    if role == 'admin':
        kb.add("👥 Xodimlar", "🎬 Loyihalar", "📢 Broadcast", "🚪 Logout")
    else:
        kb.add("🎙 Ovoz topshirish", "👤 Kabinet", "💰 Balans", "🚪 Logout")
    return kb

def back_inline_kb(callback_data="menu_main"):
    return types.InlineKeyboardMarkup().add(types.InlineKeyboardButton("⬅️ Orqaga", callback_data=callback_data))

# ==========================================
# 4. AUTH TIZIMI (LOGIN/REGISTRATION)
# ==========================================
@bot.message_handler(commands=['start'])
def start(message):
    user = get_logged_user(message.chat.id)
    if user:
        bot.send_message(message.chat.id, f"👋 Xush kelibsiz, <b>{user[2]}</b>!", reply_markup=main_menu_kb(user[8]))
    else:
        kb = types.InlineKeyboardMarkup(row_width=2)
        kb.add(types.InlineKeyboardButton("🔑 Kirish", callback_data="auth_login"),
               types.InlineKeyboardButton("📝 Ro'yxatdan o'tish", callback_data="auth_reg"))
        text = "🎬 <b>FENIKS STUDIO ELITE</b> tizimiga xush kelibsiz!\n\nDavom etish uchun o'z hisobingizga kiring yoki yangi xodim sifatida ro'yxatdan o'ting."
        bot.send_message(message.chat.id, text, reply_markup=kb)

@bot.callback_query_handler(func=lambda call: call.data.startswith('auth_'))
def auth_handler(call):
    safe_delete(call.message.chat.id, call.message.message_id)
    if call.data == "auth_reg":
        msg = bot.send_message(call.message.chat.id, "📝 <b>Ism va familiyangizni kiriting:</b>")
        bot.register_next_step_handler(msg, reg_name)
    elif call.data == "auth_login":
        msg = bot.send_message(call.message.chat.id, "🔑 <b>Loginingizni kiriting:</b>")
        bot.register_next_step_handler(msg, login_step1)

def reg_name(message):
    user_states[message.chat.id] = {'name': message.text}
    msg = bot.send_message(message.chat.id, "👤 <b>Yangi login o'ylab toping (masalan: dubber_01):</b>")
    bot.register_next_step_handler(msg, reg_login)

def reg_login(message):
    login = message.text.strip().replace(" ", "")
    conn, cur = get_db()
    cur.execute("SELECT id FROM users WHERE login = ?", (login,))
    if cur.fetchone():
        msg = bot.send_message(message.chat.id, "⚠️ Bu login band. Boshqa login kiriting:")
        bot.register_next_step_handler(msg, reg_login)
    else:
        user_states[message.chat.id]['login'] = login
        msg = bot.send_message(message.chat.id, "🔒 <b>Parol kiriting:</b>")
        bot.register_next_step_handler(msg, reg_pass)
    conn.close()

def reg_pass(message):
    safe_delete(message.chat.id, message.message_id) # Parolni o'chirib tashlaymiz (xavfsizlik)
    user_states[message.chat.id]['pass'] = hash_password(message.text)
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    kb.add(types.KeyboardButton("📞 Telefon raqamni yuborish", request_contact=True))
    msg = bot.send_message(message.chat.id, "📱 <b>Telefon raqamingizni yuboring:</b>", reply_markup=kb)
    bot.register_next_step_handler(msg, reg_final)

def reg_final(message):
    if not message.contact:
        msg = bot.send_message(message.chat.id, "Iltimos, pastdagi tugma orqali telefon raqamingizni yuboring.")
        bot.register_next_step_handler(msg, reg_final)
        return
    
    data = user_states[message.chat.id]
    conn, cur = get_db()
    try:
        with db_lock:
            cur.execute("INSERT INTO users (telegram_id, name, login, password_hash, phone) VALUES (?,?,?,?,?)",
                        (message.chat.id, data['name'], data['login'], data['pass'], message.contact.phone_number))
            conn.commit()
        bot.send_message(message.chat.id, "✅ <b>Muvaffaqiyatli ro'yxatdan o'tdingiz!</b>\nEndi tizimga kirishingiz mumkin.", reply_markup=types.ReplyKeyboardRemove())
        start(message)
    except Exception as e:
        bot.send_message(message.chat.id, f"Xatolik yuz berdi: {e}")
    finally:
        conn.close()
        user_states.pop(message.chat.id, None)

def login_step1(message):
    user_states[message.chat.id] = {'login': message.text.strip()}
    msg = bot.send_message(message.chat.id, "🔒 <b>Parolingizni kiriting:</b>")
    bot.register_next_step_handler(msg, login_step2)

def login_step2(message):
    safe_delete(message.chat.id, message.message_id) # Parolni xatdan o'chiramiz
    login = user_states[message.chat.id]['login']
    pw = hash_password(message.text)
    
    conn, cur = get_db()
    cur.execute("SELECT id, role FROM users WHERE login = ? AND password_hash = ?", (login, pw))
    user = cur.fetchone()
    
    if user:
        with db_lock:
            cur.execute("INSERT OR REPLACE INTO active_logins (telegram_id, user_id) VALUES (?,?)", (message.chat.id, user[0]))
            conn.commit()
        bot.send_message(message.chat.id, "✅ <b>Tizimga muvaffaqiyatli kirdingiz!</b>", reply_markup=main_menu_kb(user[1]))
    else:
        bot.send_message(message.chat.id, "❌ Login yoki parol noto'g'ri. Qaytadan /start bosing.")
    conn.close()
    user_states.pop(message.chat.id, None)

# ==========================================
# 5. USER PANEL FUNKSIYALARI
# ==========================================
@bot.message_handler(func=lambda m: m.text == "💰 Balans")
def show_balance(message):
    user = get_logged_user(message.chat.id)
    if not user: return
    bot.send_message(message.chat.id, f"💰 <b>Joriy balansingiz:</b> <code>{user[7]} so'm</code>")

@bot.message_handler(func=lambda m: m.text == "👤 Kabinet")
def cabinet(message):
    user = get_logged_user(message.chat.id)
    if not user: return
    text = f"👤 <b>SHAXSIY KABINET</b>\n━━━━━━━━━━━━━━━━━━━━\n🆔 <b>ID:</b> <code>{user[0]}</code>\n👤 <b>Ism:</b> {user[2]}\n🔑 <b>Login:</b> {user[3]}\n📱 <b>Tel:</b> {user[5]}\n💳 <b>Karta:</b> <code>{user[6] or 'Kiritilmagan'}</code>"
    kb = types.InlineKeyboardMarkup(row_width=1)
    kb.add(types.InlineKeyboardButton("✏️ Ismni o'zgartirish", callback_data="edit_name"),
           types.InlineKeyboardButton("💳 Karta raqamini kiritish", callback_data="edit_card"),
           types.InlineKeyboardButton("💬 Adminga murojaat", callback_data="user_support"))
    bot.send_message(message.chat.id, text, reply_markup=kb)

@bot.callback_query_handler(func=lambda call: call.data in ["edit_name", "edit_card", "user_support"])
def cabinet_actions(call):
    safe_delete(call.message.chat.id, call.message.message_id)
    if call.data == "edit_card":
        msg = bot.send_message(call.message.chat.id, "💳 <b>16 xonali karta raqamini kiriting:</b>\n<i>(Masalan: 8600123456789012)</i>", reply_markup=back_inline_kb("cancel_step"))
        bot.register_next_step_handler(msg, save_card)
    elif call.data == "edit_name":
        msg = bot.send_message(call.message.chat.id, "✏️ <b>Yangi ism-familiyangizni kiriting:</b>", reply_markup=back_inline_kb("cancel_step"))
        bot.register_next_step_handler(msg, save_name)
    elif call.data == "user_support":
        msg = bot.send_message(call.message.chat.id, "💬 <b>Rejissyorga xabaringizni yozib qoldiring:</b>", reply_markup=back_inline_kb("cancel_step"))
        bot.register_next_step_handler(msg, send_support)

def save_card(message):
    card = message.text.replace(" ", "")
    if len(card) == 16 and card.isdigit():
        conn, cur = get_db()
        with db_lock:
            cur.execute("UPDATE users SET card_number = ? WHERE telegram_id = ?", (card, message.chat.id))
            conn.commit()
        conn.close()
        bot.send_message(message.chat.id, "✅ Karta muvaffaqiyatli saqlandi.")
    else:
        msg = bot.send_message(message.chat.id, "❌ Xato karta raqami kiritildi. Qaytadan urinib ko'ring:")
        bot.register_next_step_handler(msg, save_card)

def save_name(message):
    conn, cur = get_db()
    with db_lock:
        cur.execute("UPDATE users SET name = ? WHERE telegram_id = ?", (message.text, message.chat.id))
        conn.commit()
    conn.close()
    bot.send_message(message.chat.id, "✅ Ismingiz yangilandi.")

def send_support(message):
    user = get_logged_user(message.chat.id)
    text = f"📩 #Murojaat\n👤 <b>Xodim:</b> {user[2]} (@{message.from_user.username})\n\n{message.text}"
    bot.send_message(ADMIN_GROUP_ID, text)
    bot.send_message(message.chat.id, "✅ Xabaringiz adminga yetkazildi.")

@bot.message_handler(func=lambda m: m.text == "🚪 Logout")
def logout(message):
    conn, cur = get_db()
    with db_lock:
        cur.execute("DELETE FROM active_logins WHERE telegram_id = ?", (message.chat.id,))
        conn.commit()
    conn.close()
    bot.send_message(message.chat.id, "👋 Tizimdan chiqdingiz.", reply_markup=types.ReplyKeyboardRemove())
    start(message)

# ==========================================
# 6. OVOZ TOPSHIRISH (PROJECT SYSTEM)
# ==========================================
@bot.message_handler(func=lambda m: m.text == "🎙 Ovoz topshirish")
def submit_voice_start(message):
    user = get_logged_user(message.chat.id)
    if not user: return
    
    conn, cur = get_db()
    # Adminga hamma loyiha ko'rinsin, userga faqat o'ziga biriktirilgani
    if user[8] == 'admin':
        cur.execute("SELECT id, name FROM projects")
    else:
        cur.execute('''SELECT p.id, p.name FROM projects p 
                       JOIN user_projects up ON p.id = up.project_id 
                       WHERE up.user_id = ?''', (user[0],))
    projs = cur.fetchall()
    conn.close()
    
    if not projs:
        bot.send_message(message.chat.id, "Sizga hozircha loyihalar biriktirilmagan. Rejissyorga murojaat qiling.")
        return
        
    kb = types.InlineKeyboardMarkup(row_width=1)
    for p in projs:
        kb.add(types.InlineKeyboardButton(f"🎬 {p[1]}", callback_data=f"subproj_{p[0]}_{p[1]}"))
        
    text = ("🎙 <b>Loyihani tanlang:</b>\n\n"
            "<i>Eslatma: Dublyajdan oldin SRT qatorlaridan qahramon ismlari olib tashlanganligiga "
            "va ismlar (masalan, Sin Mu, Doktor Sem) to'g'ri ijro etilganiga e'tibor bering.</i>")
    bot.send_message(message.chat.id, text, reply_markup=kb)

@bot.callback_query_handler(func=lambda call: call.data.startswith('subproj_'))
def subproj_step2(call):
    safe_delete(call.message.chat.id, call.message.message_id)
    _, p_id, p_name = call.data.split('_', 2)
    user_states[call.message.chat.id] = {'p_id': p_id, 'p_name': p_name}
    
    msg = bot.send_message(call.message.chat.id, f"🎬 Loyiha: <b>{p_name}</b>\n🔢 <b>Qism (epizod) raqamini yozing:</b>\n<i>(Faqat raqam kiriting)</i>", reply_markup=back_inline_kb("cancel_step"))
    bot.register_next_step_handler(msg, subproj_step3)

def subproj_step3(message):
    if not message.text or not message.text.isdigit():
        msg = bot.send_message(message.chat.id, "❌ Faqat raqam kiriting. Qism raqamini qayta yozing:")
        bot.register_next_step_handler(msg, subproj_step3)
        return
        
    user_states[message.chat.id]['ep'] = message.text
    msg = bot.send_message(message.chat.id, "📤 <b>Media faylni yuboring (Audio / Video / Zip):</b>", reply_markup=back_inline_kb("cancel_step"))
    bot.register_next_step_handler(msg, subproj_final)

def subproj_final(message):
    if not (message.audio or message.video or message.document or message.voice):
        msg = bot.send_message(message.chat.id, "❌ Faqat media fayl (Audio, Video yoki Document) qabul qilinadi. Qayta yuboring:")
        bot.register_next_step_handler(msg, subproj_final)
        return

    data = user_states.get(message.chat.id)
    user = get_logged_user(message.chat.id)
    if not data or not user: return
    
    conn, cur = get_db()
    cur.execute("SELECT topic_id FROM projects WHERE id = ?", (data['p_id'],))
    res = cur.fetchone()
    topic_id = res[0] if res else None
    
    # Narxni olish (Admin uchun loyihaning standart narxi, xodim uchun kelishilgan narx)
    if user[8] == 'admin':
        cur.execute("SELECT price FROM projects WHERE id = ?", (data['p_id'],))
    else:
        cur.execute("SELECT price FROM user_projects WHERE user_id = ? AND project_id = ?", (user[0], data['p_id']))
    price_res = cur.fetchone()
    price = price_res[0] if price_res else 0
    conn.close()

    caption = f"🔔 <b>YANGI ISH TOPSHIRILDI</b>\n━━━━━━━━━━━━━━━━━━━━\n👤 <b>Xodim:</b> {user[2]}\n🎬 <b>Loyiha:</b> {data['p_name']}\n🔢 <b>Qism:</b> {data['ep']}\n💰 <b>Narx:</b> {price} so'm"
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(types.InlineKeyboardButton("✅ Tasdiqlash", callback_data=f"adm_app_{user[0]}_{price}"),
           types.InlineKeyboardButton("❌ Rad etish", callback_data=f"adm_rej_{user[0]}_{price}"))

    try:
        if message.audio: bot.send_audio(ADMIN_GROUP_ID, message.audio.file_id, caption=caption, reply_markup=kb, message_thread_id=topic_id)
        elif message.video: bot.send_video(ADMIN_GROUP_ID, message.video.file_id, caption=caption, reply_markup=kb, message_thread_id=topic_id)
        elif message.document: bot.send_document(ADMIN_GROUP_ID, message.document.file_id, caption=caption, reply_markup=kb, message_thread_id=topic_id)
        elif message.voice: bot.send_voice(ADMIN_GROUP_ID, message.voice.file_id, caption=caption, reply_markup=kb, message_thread_id=topic_id)
        
        bot.send_message(message.chat.id, "✅ <b>Ishingiz Rejissyorga yuborildi!</b>\nTasdiqlangach balansingizga pul qo'shiladi.")
    except Exception as e:
        bot.send_message(message.chat.id, f"⚠️ Fayl guruhga bormadi. Admin guruh sozlamalarini tekshiring. Xato: {e}")
    finally:
        user_states.pop(message.chat.id, None)

# ==========================================
# 7. ADMIN PANEL (TASDIQLASH VA BOSHQARUV)
# ==========================================
@bot.callback_query_handler(func=lambda call: call.data.startswith('adm_'))
def admin_decision(call):
    _, action, u_id, price = call.data.split('_')
    price, u_id = int(price), int(u_id)
    
    conn, cur = get_db()
    cur.execute("SELECT telegram_id FROM users WHERE id = ?", (u_id,))
    u_tg = cur.fetchone()
    
    new_caption = call.message.caption + "\n━━━━━━━━━━━━━━━━━━━━\n"
    if action == "app":
        with db_lock:
            cur.execute("UPDATE users SET balance = balance + ? WHERE id = ?", (price, u_id))
            conn.commit()
        new_caption += "✅ <b>HOLAT: TASDIQLANDI</b>"
        if u_tg: 
            try: bot.send_message(u_tg[0], f"🎉 <b>Tabriklaymiz!</b> Ishingiz tasdiqlandi va hisobingizga <code>+{price} so'm</code> qo'shildi.")
            except: pass
    else:
        new_caption += "❌ <b>HOLAT: RAD ETILDI</b>"
        if u_tg:
            try: bot.send_message(u_tg[0], f"⚠️ <b>Ishingiz rad etildi.</b> Sifatni tekshirib qaytadan topshiring.")
            except: pass
            
    conn.close()
    try: bot.edit_message_caption(new_caption, call.message.chat.id, call.message.message_id)
    except: pass

@bot.message_handler(func=lambda m: m.text == "📢 Broadcast")
def admin_broadcast(message):
    user = get_logged_user(message.chat.id)
    if not user or user[8] != 'admin': return
    msg = bot.send_message(message.chat.id, "📢 <b>Barcha xodimlarga yuboriladigan xabarni yozing:</b>", reply_markup=back_inline_kb("cancel_step"))
    bot.register_next_step_handler(msg, process_broadcast)

def process_broadcast(message):
    conn, cur = get_db()
    cur.execute("SELECT telegram_id FROM active_logins")
    users = cur.fetchall()
    conn.close()
    
    count = 0
    for tg in users:
        try:
            bot.send_message(tg[0], f"📢 <b>REJISSYORDAN XABAR:</b>\n━━━━━━━━━━━━━━━━━━━━\n{message.text}")
            count += 1
        except: pass
    bot.send_message(message.chat.id, f"✅ Xabar faol {count} ta xodimga yetkazildi.")

@bot.message_handler(func=lambda m: m.text == "👥 Xodimlar")
def admin_workers(message):
    user = get_logged_user(message.chat.id)
    if not user or user[8] != 'admin': return
    
    conn, cur = get_db()
    cur.execute("SELECT id, name, balance FROM users WHERE role = 'user'")
    workers = cur.fetchall()
    conn.close()
    
    text = "👥 <b>XODIMLAR RO'YXATI:</b>\n━━━━━━━━━━━━━━━━━━━━\n"
    if not workers: text += "<i>Hali xodimlar yo'q. Umarbek, AMIN, Zilola-chan va boshqalar ro'yxatdan o'tishlari kerak.</i>"
    for w in workers:
        text += f"👤 <b>{w[1]}</b> | 💰 {w[2]} so'm\n"
    bot.send_message(message.chat.id, text)

@bot.message_handler(func=lambda m: m.text == "🎬 Loyihalar")
def admin_projects_menu(message):
    user = get_logged_user(message.chat.id)
    if not user or user[8] != 'admin': return
    
    conn, cur = get_db()
    cur.execute("SELECT id, name, price FROM projects")
    projs = cur.fetchall()
    conn.close()
    
    text = "🎬 <b>BAZADAGI LOYIHALAR:</b>\n━━━━━━━━━━━━━━━━━━━━\n"
    for p in projs: text += f"📌 {p[1]} <i>({p[2]} so'm)</i>\n"
    
    kb = types.InlineKeyboardMarkup().add(types.InlineKeyboardButton("➕ Yangi loyiha qo'shish", callback_data="add_proj"))
    bot.send_message(message.chat.id, text, reply_markup=kb)

@bot.callback_query_handler(func=lambda call: call.data == "add_proj")
def add_new_project_step1(call):
    safe_delete(call.message.chat.id, call.message.message_id)
    msg = bot.send_message(call.message.chat.id, "➕ <b>Yangi loyiha nomini yozing:</b>", reply_markup=back_inline_kb("cancel_step"))
    bot.register_next_step_handler(msg, add_new_project_step2)

def add_new_project_step2(message):
    user_states[message.chat.id] = {'p_name': message.text}
    msg = bot.send_message(message.chat.id, "💰 <b>Har bir qism uchun to'lanadigan narxni yozing (faqat raqam):</b>")
    bot.register_next_step_handler(msg, add_new_project_final)

def add_new_project_final(message):
    if not message.text.isdigit():
        msg = bot.send_message(message.chat.id, "❌ Faqat raqam kiriting. Qayta yozing:")
        bot.register_next_step_handler(msg, add_new_project_final)
        return
        
    p_name = user_states[message.chat.id]['p_name']
    p_price = int(message.text)
    
    # Topic yaratishga urinish
    topic_id = None
    try:
        topic = bot.create_forum_topic(chat_id=ADMIN_GROUP_ID, name=p_name)
        topic_id = topic.message_thread_id
    except: pass # Guruhda Topic yoqilmagan bo'lsa, o'tkazib yuboradi

    conn, cur = get_db()
    with db_lock:
        cur.execute("INSERT INTO projects (name, price, topic_id) VALUES (?,?,?)", (p_name, p_price, topic_id))
        conn.commit()
    conn.close()
    
    bot.send_message(message.chat.id, f"✅ <b>{p_name}</b> loyihasi muvaffaqiyatli qo'shildi!")
    user_states.pop(message.chat.id, None)

@bot.callback_query_handler(func=lambda call: call.data == "cancel_step")
def cancel_any_step(call):
    bot.clear_step_handler_by_chat_id(chat_id=call.message.chat.id)
    user_states.pop(call.message.chat.id, None)
    safe_delete(call.message.chat.id, call.message.message_id)
    bot.send_message(call.message.chat.id, "❌ Amal bekor qilindi.")

# ==========================================
# 8. RENDER/RAILWAY UCHUN WEB SERVER
# ==========================================
class DummyHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/plain')
        self.end_headers()
        self.wfile.write(b"Feniks Studio Elite Boti faol!")

def run_dummy_server():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(('0.0.0.0', port), DummyHandler)
    server.serve_forever()

threading.Thread(target=run_dummy_server, daemon=True).start()

# ==========================================
# 9. BOTNI ISHGA TUSHIRISH (INFINITY POLLING)
# ==========================================
print("Feniks Studio Elite bot ishga tushirildi!")
while True:
    try:
        bot.infinity_polling(timeout=10, long_polling_timeout=5, skip_pending=True)
    except Exception as e:
        print(f"Xatolik yuz berdi: {e}")
        time.sleep(5)
