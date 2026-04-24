import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
import sqlite3
import threading
import time
import os
from http.server import BaseHTTPRequestHandler, HTTPServer

# ==========================================
# 1. KONFIGURATSIYA (Xavfsiz)
# ==========================================
# Railway Variables bo'limiga qo'shishni unutmang!
TOKEN = os.environ.get('BOT_TOKEN', '7709322312:AAH97S0tq54R-VfDCHp_X3XOf6I-pY_X5kI')
ADMIN_GROUP_ID = int(os.environ.get('ADMIN_GROUP_ID', -1002447942125))

bot = telebot.TeleBot(TOKEN, parse_mode='HTML')
db_lock = threading.Lock()

# BAZA YO'LI (Volume uchun)
DB_DIR = "/app/data"
if not os.path.exists(DB_DIR):
    os.makedirs(DB_DIR, exist_ok=True)
DB_PATH = os.path.join(DB_DIR, "feniks_final.db")

# ==========================================
# 2. MA'LUMOTLAR BAZASI
# ==========================================
def init_db():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    cursor = conn.cursor()
    with db_lock:
        # Foydalanuvchilar jadvali
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                telegram_id INTEGER UNIQUE,
                name TEXT,
                phone TEXT,
                login TEXT UNIQUE,
                password TEXT,
                balance INTEGER DEFAULT 0,
                card_number TEXT,
                role TEXT DEFAULT 'worker',
                status TEXT DEFAULT 'pending'
            )
        ''')
        
        # Loyihalar jadvali
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS projects (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT,
                topic_id INTEGER
            )
        ''')
        
        # Xodimga biriktirilgan loyihalar
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS user_projects (
                user_id INTEGER,
                project_id INTEGER,
                price INTEGER DEFAULT 0,
                FOREIGN KEY(user_id) REFERENCES users(id),
                FOREIGN KEY(project_id) REFERENCES projects(id)
            )
        ''')
        
        # Adminni tekshirish yoki yaratish
        cursor.execute("SELECT COUNT(*) FROM users WHERE role = 'admin'")
        if cursor.fetchone()[0] == 0:
            # Standart admin: login: admin, parol: admin777
            cursor.execute("INSERT INTO users (name, login, password, role, status) VALUES ('Rejissyor', 'admin', 'admin777', 'admin', 'active')")
        
        conn.commit()
    return conn, cursor

conn, cursor = init_db()

# ==========================================
# 3. YORDAMCHI FUNKSIYALAR
# ==========================================
def get_user_by_tg(tg_id):
    with db_lock:
        cursor.execute("SELECT * FROM users WHERE telegram_id = ? AND status = 'active'", (tg_id,))
        return cursor.fetchone()

def safe_delete(chat_id, msg_id):
    try:
        bot.delete_message(chat_id, msg_id)
    except:
        pass

def delete_later(chat_id, msg_id, delay=3):
    def task():
        time.sleep(delay)
        safe_delete(chat_id, msg_id)
    threading.Thread(target=task).start()

# ==========================================
# 4. RO'YXATDAN O'TISH VA KIRISH (AUTH)
# ==========================================
@bot.message_handler(commands=['start'])
def start_handler(message):
    user = get_user_by_tg(message.chat.id)
    if user:
        show_main_menu(message.chat.id, user)
    else:
        text = "<b>FENIKS STUDIO | ISHCHI TIZIMI</b>\n━━━━━━━━━━━━━\nAssalomu alaykum! Tizimga kirish uchun tanlang:"
        markup = InlineKeyboardMarkup(row_width=2).add(
            InlineKeyboardButton("🔑 Kirish", callback_data="auth_login"),
            InlineKeyboardButton("📝 Ro'yxatdan o'tish", callback_data="auth_reg")
        )
        bot.send_message(message.chat.id, text, reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('auth_'))
def auth_callback(call):
    action = call.data.split('_')[1]
    safe_delete(call.message.chat.id, call.message.message_id)
    
    if action == "login":
        msg = bot.send_message(call.message.chat.id, "👤 <b>Loginingizni kiriting:</b>")
        bot.register_next_step_handler(msg, login_get_username)
    elif action == "reg":
        msg = bot.send_message(call.message.chat.id, "👤 <b>Ism va familiyangizni yozing:</b>\n(Masalan: Shohrux Toirov)")
        bot.register_next_step_handler(msg, reg_get_name)

# --- Login Mantiqi ---
def login_get_username(message):
    login = message.text.strip()
    msg = bot.send_message(message.chat.id, "🔒 <b>Parolingizni kiriting:</b>")
    bot.register_next_step_handler(msg, login_check_pass, login)

def login_check_pass(message, login):
    password = message.text.strip()
    with db_lock:
        cursor.execute("SELECT * FROM users WHERE login = ? AND password = ?", (login, password))
        user = cursor.fetchone()
    
    if user:
        if user[9] == 'pending':
            bot.send_message(message.chat.id, "⏳ <b>Sizning arizangiz hali ko'rib chiqilmoqda.</b>\nAdmin tasdiqlaganidan keyin xabar boradi.")
        else:
            with db_lock:
                cursor.execute("UPDATE users SET telegram_id = ? WHERE id = ?", (message.chat.id, user[0]))
                conn.commit()
            bot.send_message(message.chat.id, "✅ Xush kelibsiz!")
            show_main_menu(message.chat.id, user)
    else:
        bot.send_message(message.chat.id, "❌ Login yoki parol xato! Qayta urinish uchun /start bosing.")

# --- Ro'yxatdan o'tish Mantiqi ---
def reg_get_name(message):
    name = message.text.strip()
    markup = ReplyKeyboardMarkup(one_time_keyboard=True, resize_keyboard=True)
    markup.add(KeyboardButton("📱 Telefon raqamni yuborish", request_contact=True))
    msg = bot.send_message(message.chat.id, f"Xursandmiz, {name}! Endi pastdagi tugmani bosib telefon raqamingizni yuboring:", reply_markup=markup)
    bot.register_next_step_handler(msg, reg_get_phone, name)

def reg_get_phone(message, name):
    if not message.contact:
        msg = bot.send_message(message.chat.id, "❌ Iltimos, tugmani bosing!")
        bot.register_next_step_handler(msg, reg_get_phone, name)
        return
    phone = message.contact.phone_number
    msg = bot.send_message(message.chat.id, "📝 <b>O'zingiz uchun unikal Login tanlang:</b>\n(Faqat inglizcha harf va raqamlar)", reply_markup=ReplyKeyboardRemove())
    bot.register_next_step_handler(msg, reg_get_login, name, phone)

def reg_get_login(message, name, phone):
    login = message.text.strip()
    with db_lock:
        cursor.execute("SELECT id FROM users WHERE login = ?", (login,))
        if cursor.fetchone():
            msg = bot.send_message(message.chat.id, "⚠️ Bu login band! Boshqa login yozing:")
            bot.register_next_step_handler(msg, reg_get_login, name, phone)
            return
    msg = bot.send_message(message.chat.id, "🔒 <b>Kirish uchun murakkab parol o'rnating:</b>")
    bot.register_next_step_handler(msg, reg_get_pass, name, phone, login)

def reg_get_pass(message, name, phone, login):
    password = message.text.strip()
    with db_lock:
        cursor.execute("INSERT INTO users (name, phone, login, password, status) VALUES (?, ?, ?, ?, 'pending')", (name, phone, login, password))
        conn.commit()
        user_id = cursor.lastrowid
    
    bot.send_message(message.chat.id, "✅ <b>Arizangiz muvaffaqiyatli topshirildi!</b>\nRejissyor tasdiqlaganidan keyin tizimdan foydalana olasiz.")
    
    # Adminga so'rov yuborish
    admin_text = (f"🆕 <b>YANGI ARIZA</b>\n━━━━━━━━━━━━━\n"
                  f"👤 Ism: {name}\n"
                  f"📞 Tel: {phone}\n"
                  f"🔑 Login: <code>{login}</code>\n"
                  f"🔒 Parol: <code>{password}</code>")
    markup = InlineKeyboardMarkup().add(
        InlineKeyboardButton("✅ Tasdiqlash", callback_data=f"adm_appr_{user_id}"),
        InlineKeyboardButton("❌ Rad etish", callback_data=f"adm_reje_{user_id}")
    )
    bot.send_message(ADMIN_GROUP_ID, admin_text, reply_markup=markup)

# ==========================================
# 5. ADMIN TASDIQLASHI
# ==========================================
@bot.callback_query_handler(func=lambda call: call.data.startswith(('adm_appr_', 'adm_reje_')))
def admin_decision(call):
    action, uid = call.data.split('_')[1], call.data.split('_')[-1]
    if action == "appr":
        with db_lock:
            cursor.execute("UPDATE users SET status = 'active' WHERE id = ?", (uid,))
            cursor.execute("SELECT telegram_id, name FROM users WHERE id = ?", (uid,))
            data = cursor.fetchone()
            conn.commit()
        bot.edit_message_text(f"✅ {data[1]} tasdiqlandi!", call.message.chat.id, call.message.message_id)
        if data[0]:
            bot.send_message(data[0], "🎉 <b>Tabriklaymiz!</b> Arizangiz tasdiqlandi. Endi /start bosing va tizimga kiring.")
    else:
        with db_lock:
            cursor.execute("DELETE FROM users WHERE id = ?", (uid,))
            conn.commit()
        bot.edit_message_text("❌ Ariza rad etildi va o'chirildi.", call.message.chat.id, call.message.message_id)

# ==========================================
# 6. ASOSIY MENYU
# ==========================================
def show_main_menu(chat_id, user_data):
    # user_data: (id, tg_id, name, phone, login, pass, balance, card, role, status)
    text = (f"<b>FENIKS STUDIO TIZIMI</b> 👋\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"👤 <b>Xodim:</b> <code>{user_data[2]}</code>\n"
            f"💰 <b>Balans:</b> <code>{user_data[6]:,} so'm</code>\n"
            f"━━━━━━━━━━━━━━━━━━━━")
    
    markup = InlineKeyboardMarkup(row_width=1).add(
        InlineKeyboardButton("🎙 Ovoz topshirish", callback_data="menu_submit"),
        InlineKeyboardButton("👤 Shaxsiy kabinet", callback_data="menu_cabinet")
    )
    
    if user_data[8] == 'admin':
        markup.add(InlineKeyboardButton("👑 Admin Panel", callback_data="admin_main"))
    
    # Video/GIF yuborish (agar feniks.mp4 bo'lsa)
    try:
        with open('feniks.mp4', 'rb') as video:
            bot.send_video(chat_id, video, caption=text, reply_markup=markup)
    except:
        bot.send_message(chat_id, text, reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data == "menu_main")
def back_to_main(call):
    user = get_user_by_tg(call.message.chat.id)
    if user:
        safe_delete(call.message.chat.id, call.message.message_id)
        show_main_menu(call.message.chat.id, user)

# ==========================================
# 7. XODIM FUNKSIYALARI
# ==========================================
@bot.callback_query_handler(func=lambda call: call.data.startswith('menu_'))
def worker_menu_handler(call):
    user = get_user_by_tg(call.message.chat.id)
    if not user: return
    
    if call.data == "menu_cabinet":
        text = (f"👤 <b>SHAXSIY KABINET</b>\n"
                f"━━━━━━━━━━━━━\n"
                f"🔑 Login: <code>{user[4]}</code>\n"
                f"📞 Tel: <code>{user[3]}</code>\n"
                f"💳 Karta: <code>{user[7] or 'Kiritilmagan'}</code>")
        markup = InlineKeyboardMarkup(row_width=1).add(
            InlineKeyboardButton("📂 Loyihalarim", callback_data="cab_projs"),
            InlineKeyboardButton("✏️ Ismni o'zgartirish", callback_data="cab_name"),
            InlineKeyboardButton("💳 Karta kiritish", callback_data="cab_card"),
            InlineKeyboardButton("🚪 Chiqish (Log out)", callback_data="cab_logout"),
            InlineKeyboardButton("⬅️ Orqaga", callback_data="menu_main")
        )
        bot.edit_message_caption(chat_id=call.message.chat.id, message_id=call.message.message_id, caption=text, reply_markup=markup)

    elif call.data == "menu_submit":
        with db_lock:
            cursor.execute('''SELECT p.id, p.name FROM projects p 
                            JOIN user_projects up ON p.id = up.project_id 
                            WHERE up.user_id = ?''', (user[0],))
            projs = cursor.fetchall()
        
        if not projs:
            bot.answer_callback_query(call.id, "Sizga hali loyiha biriktirilmagan!", show_alert=True)
            return
            
        text = "🎬 <b>Loyiha tanlang:</b>"
        markup = InlineKeyboardMarkup(row_width=1)
        for p in projs:
            markup.add(InlineKeyboardButton(p[1], callback_data=f"sub_p_{p[0]}"))
        markup.add(InlineKeyboardButton("⬅️ Orqaga", callback_data="menu_main"))
        bot.edit_message_caption(chat_id=call.message.chat.id, message_id=call.message.message_id, caption=text, reply_markup=markup)

# --- Ovoz topshirish jarayoni ---
@bot.callback_query_handler(func=lambda call: call.data.startswith('sub_p_'))
def sub_get_episode(call):
    pid = call.data.split('_')[2]
    msg = bot.send_message(call.message.chat.id, "🔢 <b>Qism raqamini yozing:</b>")
    bot.register_next_step_handler(msg, sub_get_file, pid)

def sub_get_file(message, pid):
    episode = message.text
    msg = bot.send_message(message.chat.id, "📤 <b>Tayyor faylni yuboring:</b>\n(Audio, Video yoki Dokument)")
    bot.register_next_step_handler(msg, sub_final, pid, episode)

def sub_final(message, pid, episode):
    user = get_user_by_tg(message.chat.id)
    with db_lock:
        cursor.execute("SELECT price FROM user_projects WHERE user_id = ? AND project_id = ?", (user[0], pid))
        price = cursor.fetchone()[0]
        cursor.execute("SELECT name, topic_id FROM projects WHERE id = ?", (pid,))
        p_data = cursor.fetchone()
        
    # Balansni oshirish
    with db_lock:
        cursor.execute("UPDATE users SET balance = balance + ? WHERE id = ?", (price, user[0]))
        conn.commit()

    # Adminga (Topicga) yuborish
    caption = (f"🎙 <b>YANGI ISH TOPSHIRILDI</b>\n"
               f"━━━━━━━━━━━━━\n"
               f"👤 Xodim: {user[2]}\n"
               f"🎬 Loyiha: {p_data[0]}\n"
               f"🔢 Qism: {episode}\n"
               f"💰 To'lov: +{price:,} so'm")
    
    markup = InlineKeyboardMarkup().add(InlineKeyboardButton("❌ Rad etish", callback_data=f"rej_work_{user[0]}_{price}_{episode}_{pid}"))
    
    try:
        if message.audio: bot.send_audio(ADMIN_GROUP_ID, message.audio.file_id, caption=caption, message_thread_id=p_data[1], reply_markup=markup)
        elif message.voice: bot.send_voice(ADMIN_GROUP_ID, message.voice.file_id, caption=caption, message_thread_id=p_data[1], reply_markup=markup)
        elif message.video: bot.send_video(ADMIN_GROUP_ID, message.video.file_id, caption=caption, message_thread_id=p_data[1], reply_markup=markup)
        else: bot.send_document(ADMIN_GROUP_ID, message.document.file_id, caption=caption, message_thread_id=p_data[1], reply_markup=markup)
        
        bot.send_message(message.chat.id, f"✅ Ish qabul qilindi! Balansingizga {price:,} so'm qo'shildi.")
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Xatolik! Fayl guruhga bormadi: {e}")

# --- Kabinet amallari ---
@bot.callback_query_handler(func=lambda call: call.data.startswith('cab_'))
def cabinet_actions(call):
    user = get_user_by_tg(call.message.chat.id)
    action = call.data.split('_')[1]
    
    if action == "logout":
        with db_lock:
            cursor.execute("UPDATE users SET telegram_id = NULL WHERE id = ?", (user[0],))
            conn.commit()
        bot.edit_message_text("👋 Tizimdan chiqdingiz. Qayta kirish uchun /start", call.message.chat.id, call.message.message_id)
        
    elif action == "card":
        msg = bot.send_message(call.message.chat.id, "💳 16 xonali karta raqamingizni yozing:")
        bot.register_next_step_handler(msg, save_card)

def save_card(message):
    card = message.text.replace(" ", "")
    if len(card) == 16 and card.isdigit():
        with db_lock:
            cursor.execute("UPDATE users SET card_number = ? WHERE telegram_id = ?", (card, message.chat.id))
            conn.commit()
        bot.send_message(message.chat.id, "✅ Karta saqlandi!")
    else:
        bot.send_message(message.chat.id, "❌ Karta raqami xato.")

# ==========================================
# 8. ADMIN PANEL FUNKSIYALARI
# ==========================================
@bot.callback_query_handler(func=lambda call: call.data.startswith('admin_'))
def admin_main_handler(call):
    user = get_user_by_tg(call.message.chat.id)
    if user[8] != 'admin': return
    
    action = call.data.split('_')[1]
    
    if action == "main":
        text = "👑 <b>REJISSYOR BOSHQARUV PANELI</b>"
        markup = InlineKeyboardMarkup(row_width=1).add(
            InlineKeyboardButton("🎬 Loyihalar", callback_data="admin_projs"),
            InlineKeyboardButton("👥 Xodimlar", callback_data="admin_workers"),
            InlineKeyboardButton("📢 Ommaviy xabar", callback_data="admin_bc"),
            InlineKeyboardButton("⬅️ Orqaga", callback_data="menu_main")
        )
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup)

    elif action == "projs":
        with db_lock:
            cursor.execute("SELECT * FROM projects")
            projs = cursor.fetchall()
        text = "🎬 <b>LOYIHALAR RO'YXATI</b>"
        markup = InlineKeyboardMarkup(row_width=1)
        for p in projs:
            markup.add(InlineKeyboardButton(f"⚙️ {p[1]}", callback_data=f"ap_view_{p[0]}"))
        markup.add(InlineKeyboardButton("➕ Yangi loyiha", callback_data="admin_addproj"))
        markup.add(InlineKeyboardButton("⬅️ Orqaga", callback_data="admin_main"))
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup)

    elif action == "addproj":
        msg = bot.send_message(call.message.chat.id, "🎬 <b>Yangi loyiha nomini yozing:</b>\n(Guruhda Topic ham ochiladi)")
        bot.register_next_step_handler(msg, admin_save_proj)

    elif action == "bc":
        msg = bot.send_message(call.message.chat.id, "📢 <b>Barcha xodimlarga yuboriladigan xabarni yozing:</b>")
        bot.register_next_step_handler(msg, admin_broadcast)

# --- Loyihani saqlash va Topic ochish ---
def admin_save_proj(message):
    name = message.text
    try:
        topic = bot.create_forum_topic(ADMIN_GROUP_ID, name)
        tid = topic.message_thread_id
    except:
        tid = None
        bot.send_message(message.chat.id, "⚠️ Topic ochilmadi (Guruhda ruxsat yo'q yoki Forum emas).")
    
    with db_lock:
        cursor.execute("INSERT INTO projects (name, topic_id) VALUES (?, ?)", (name, tid))
        conn.commit()
    bot.send_message(message.chat.id, f"✅ Loyiha '{name}' yaratildi.")

# --- Ommaviy xabar ---
def admin_broadcast(message):
    with db_lock:
        cursor.execute("SELECT telegram_id FROM users WHERE status = 'active' AND telegram_id IS NOT NULL")
        users = cursor.fetchall()
    count = 0
    for u in users:
        try:
            bot.send_message(u[0], f"📢 <b>ADMINXABAR:</b>\n━━━━━━━━━━━━━\n{message.text}")
            count += 1
        except: pass
    bot.send_message(message.chat.id, f"✅ Xabar {count} ta xodimga yuborildi.")

# --- Xodimlarni boshqarish ---
@bot.callback_query_handler(func=lambda call: call.data == "admin_workers")
def admin_workers_list(call):
    with db_lock:
        cursor.execute("SELECT id, name, balance FROM users WHERE status = 'active'")
        ws = cursor.fetchall()
    text = "👥 <b>XODIMLAR:</b>"
    markup = InlineKeyboardMarkup(row_width=2)
    for w in ws:
        markup.add(InlineKeyboardButton(f"{w[1]} ({w[2]:,})", callback_data=f"aw_edit_{w[0]}"))
    markup.add(InlineKeyboardButton("⬅️ Orqaga", callback_data="admin_main"))
    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('aw_edit_'))
def admin_worker_detail(call):
    uid = call.data.split('_')[2]
    with db_lock:
        cursor.execute("SELECT * FROM users WHERE id = ?", (uid,))
        u = cursor.fetchone()
    text = (f"👤 <b>Xodim:</b> {u[2]}\n"
            f"📞 Tel: {u[3]}\n"
            f"💰 Balans: {u[6]:,} so'm\n"
            f"💳 Karta: {u[7] or 'Yo'q'}")
    markup = InlineKeyboardMarkup(row_width=1).add(
        InlineKeyboardButton("➕ Loyihaga qo'shish", callback_data=f"aw_addp_{uid}"),
        InlineKeyboardButton("💸 Maosh to'lash", callback_data=f"aw_pay_{uid}"),
        InlineKeyboardButton("❌ O'chirish", callback_data=f"aw_del_{uid}"),
        InlineKeyboardButton("⬅️ Orqaga", callback_data="admin_workers")
    )
    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup)

# --- Loyihaga aktyor qo'shish va narx belgilash ---
@bot.callback_query_handler(func=lambda call: call.data.startswith('aw_addp_'))
def admin_add_p_to_w(call):
    uid = call.data.split('_')[2]
    with db_lock:
        cursor.execute("SELECT * FROM projects")
        projs = cursor.fetchall()
    markup = InlineKeyboardMarkup(row_width=1)
    for p in projs:
        markup.add(InlineKeyboardButton(p[1], callback_data=f"aw_setp_{uid}_{p[0]}"))
    bot.edit_message_text("Qaysi loyihaga qo'shamiz?", call.message.chat.id, call.message.message_id, reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('aw_setp_'))
def admin_set_price(call):
    _, _, uid, pid = call.data.split('_')
    msg = bot.send_message(call.message.chat.id, "💰 <b>Ushbu aktyor uchun bir qism narxini yozing:</b>\n(Faqat raqam, masalan: 45000)")
    bot.register_next_step_handler(msg, admin_save_user_proj, uid, pid)

def admin_save_user_proj(message, uid, pid):
    price = int(message.text.replace(" ", ""))
    with db_lock:
        cursor.execute("INSERT OR REPLACE INTO user_projects (user_id, project_id, price) VALUES (?, ?, ?)", (uid, pid, price))
        conn.commit()
    bot.send_message(message.chat.id, "✅ Loyiha va narx biriktirildi.")

# ==========================================
# 9. RENDER/RAILWAY UCHUN SERVER
# ==========================================
class WebHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200); self.send_header('Content-type','text/plain'); self.end_headers()
        self.wfile.write(b"Feniks System Online")

def start_server():
    port = int(os.environ.get("PORT", 8080))
    HTTPServer(('0.0.0.0', port), WebHandler).serve_forever()

if __name__ == "__main__":
    threading.Thread(target=start_server, daemon=True).start()
    print("Feniks Studio Bot ishga tushdi...")
    bot.infinity_polling(skip_pending=True)
