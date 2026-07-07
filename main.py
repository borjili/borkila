import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
import requests
import re
import time
import json
import base64
import threading

# ================= إعدادات البوت (تأكد من صحتها) =================
BOT_TOKEN = "8904936753:AAFDPuq_UOYEYoNEBsN5fkD_mZSB4WPGxCc"

P2P_CONFIG = {
    "apiKey": "8CK-5Z-SLV-7Z8-7ZC-H5R-RJC-825",
    "username": "borjili",
    "site": "p2punlocker.com"
}

xxx_CONFIG = {
    "apiKey": "33D-55C-ACU-VST-EE8-MIZ-KIU-JCM",
    "username": "apps48.02",
    "site": "xxx.com"
}

SUPABASE_URL = "https://ytmuiiprruajxdgmrxev.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Inl0bXVpaXBycnVhanhkZ21yeGV2Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODAyMzYzNDEsImV4cCI6MjA5NTgxMjM0MX0.Ay6hrOcaFxZLDhpjuSOPTgI9P9DPP--PH6SiG7qv8Qk"

ACCOUNT_IP = "105.78.67.167"

# ================= الخدمات =================
P2P_SERVICES = {
    "320": {"name": "Xiaomi Official Remove Mi Account CLEAN EUROPE AUTO", "type": "imei"},
    "21830": {"name": "FMI On/Off Status", "type": "imei"},
    "21047": {
        "name": "AH-AUTH Auth Credit",
        "type": "imei_custom",
        "id_label": "Email",
        "id_hint": "أرسل البريد الإلكتروني المسجل في AH-AUTH",
        "qnt_min": 5,
        "qnt_max": 5000,
    },
}
xxx_SERVICES = {
    "17447": {"name": "Full GSX Report", "type": "imei"},
}

CHECK_INTERVAL = 20

# ================= متغيرات النظام =================
ADMIN_ID = None
ALLOWED_USERS = set()
PENDING_REQUESTS = {}
user_states = {}
pending_orders = {}
orders_lock = threading.Lock()

bot = telebot.TeleBot(BOT_TOKEN)

# ================= Supabase =================
SUPABASE_HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
}

def supabase_get(path, query=""):
    url = f"{SUPABASE_URL}/rest/v1/{path}?{query}"
    try:
        r = requests.get(url, headers=SUPABASE_HEADERS, timeout=30)
        if r.status_code == 200: return r.json()
        print(f"⚠️ Supabase GET Error: {r.status_code}")
        return None
    except Exception as e:
        print(f"❌ Supabase GET Exception: {e}")
        return None

def supabase_post(path, payload):
    url = f"{SUPABASE_URL}/rest/v1/{path}"
    headers = dict(SUPABASE_HEADERS)
    headers["Prefer"] = "return=representation"
    try:
        r = requests.post(url, headers=headers, json=payload, timeout=30)
        if r.status_code in (200, 201): return r.json()
        print(f"⚠️ Supabase POST Error: {r.status_code} - {r.text}")
        return None
    except Exception as e:
        print(f"❌ Supabase POST Exception: {e}")
        return None

def supabase_patch(path, payload, query=""):
    url = f"{SUPABASE_URL}/rest/v1/{path}?{query}"
    try:
        r = requests.patch(url, headers=SUPABASE_HEADERS, json=payload, timeout=30)
        return r.status_code in (200, 204)
    except Exception as e:
        print(f"❌ Supabase PATCH Exception: {e}")
        return False

def supabase_delete(path, query=""):
    url = f"{SUPABASE_URL}/rest/v1/{path}?{query}"
    try:
        r = requests.delete(url, headers=SUPABASE_HEADERS, timeout=30)
        return r.status_code in (200, 204)
    except Exception as e:
        print(f"❌ Supabase DELETE Exception: {e}")
        return False

# ================= إدارة المستخدمين =================
def add_allowed_user(telegram_id, username="", added_by=""):
    global ALLOWED_USERS
    ALLOWED_USERS.add(str(telegram_id))
    supabase_post("allowed_users", {
        "telegram_id": str(telegram_id),
        "username": username or "بدون يوزر",
        "added_by": str(added_by)
    })

def remove_allowed_user(telegram_id):
    global ALLOWED_USERS
    tid = str(telegram_id)
    if tid in ALLOWED_USERS: ALLOWED_USERS.remove(tid)
    supabase_delete("allowed_users", f"telegram_id=eq.{tid}")

def load_bot_data():
    global ADMIN_ID, ALLOWED_USERS
    print("🔄 جاري تحميل البيانات من Supabase...")
    
    settings = supabase_get("bot_settings", "key=eq.admin_id&select=value")
    if settings: 
        ADMIN_ID = str(settings[0].get("value"))
        print(f"✅ تم تحميل الأدمن: {ADMIN_ID}")
    
    users = supabase_get("allowed_users", "select=telegram_id")
    if users: 
        ALLOWED_USERS = {str(u["telegram_id"]) for u in users}
        print(f"✅ تم تحميل {len(ALLOWED_USERS)} مستخدم مفعّل.")
    
    active_orders = supabase_get("orders", "status=eq.In%20Process&select=reference_id,telegram_id,api_source")
    if active_orders:
        with orders_lock:
            for order in active_orders:
                pending_orders[str(order['reference_id'])] = {"chat_id": order['telegram_id'], "api": order['api_source']}
        print(f"✅ تم استعادة {len(active_orders)} طلب للمراقبة.")

def is_authorized(user_id):
    return str(user_id) == ADMIN_ID or str(user_id) in ALLOWED_USERS

def is_admin(user_id):
    return ADMIN_ID and str(user_id) == str(ADMIN_ID)

# ================= وظائف API السيرفرات =================
def api_post_generic(config, payload):
    payload.update({"username": config["username"], "apiaccesskey": config["apiKey"], "requestformat": "JSON"})
    headers = {"User-Agent": "Mozilla/5.0", "X-Forwarded-For": ACCOUNT_IP}
    try:
        r = requests.post(f"https://{config['site']}/api/index.php", data=payload, headers=headers, timeout=30)
        return r.json()
    except Exception as e:
        print(f"❌ API Error ({config['site']}): {e}")
        return {"ERROR": [{"MESSAGE": "خطأ في الاتصال بالسيرفر"}]}

def extract_result(data):
    return data.get("CODE") or data.get("RESULT") or data.get("REPLY") or data.get("RESPONSE") or data.get("COMMENTS") or ""

def clean_result(text):
    if not text: return ""
    text = str(text).replace("<br>", "\n").replace("<br/>", "\n").replace("&nbsp;", " ")
    text = re.sub(r'<[^>]+>', '', text)
    return text.strip()

# ================= الواجهات =================
def main_keyboard():
    markup = ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row(KeyboardButton("🛒 Place an order"))
    return markup

def admin_keyboard():
    markup = ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row(KeyboardButton("🎛 لوحة التحكم"), KeyboardButton("🛒 Place an order"))
    return markup

def admin_panel_keyboard():
    markup = InlineKeyboardMarkup()
    markup.row(InlineKeyboardButton("👥 المستخدمون", callback_data="panel_users"), InlineKeyboardButton("📊 الإحصائيات", callback_data="panel_stats"))
    markup.row(InlineKeyboardButton("⏳ طلبات معلقة", callback_data="panel_pending"), InlineKeyboardButton("💰 أرصدة السيرفر", callback_data="panel_balance"))
    markup.row(InlineKeyboardButton("📋 سجل العمليات العام", callback_data="panel_all_orders"))
    return markup

# ================= المعالجات =================
@bot.message_handler(commands=['start'])
def start_cmd(message):
    uid = str(message.from_user.id)
    uname = message.from_user.username or message.from_user.first_name
    global ADMIN_ID
    
    if ADMIN_ID is None:
        ADMIN_ID = uid
        supabase_post("bot_settings", {"key": "admin_id", "value": uid})
        bot.send_message(message.chat.id, "✅ تم تعيينك كأدمن للبوت.", reply_markup=admin_keyboard())
        return

    if is_admin(uid):
        bot.send_message(message.chat.id, "👋 أهلاً بك يا أدمن.", reply_markup=admin_keyboard())
    elif is_authorized(uid):
        bot.send_message(message.chat.id, "👋 أهلاً بك في البوت!", reply_markup=main_keyboard())
    else:
        if uid not in PENDING_REQUESTS:
            PENDING_REQUESTS[uid] = {"name": message.from_user.first_name, "username": uname}
            bot.send_message(message.chat.id, "⏳ طلب انضمامك قيد المراجعة من قبل الإدارة.")
            if ADMIN_ID:
                markup = InlineKeyboardMarkup()
                markup.row(InlineKeyboardButton("✅ موافقة", callback_data=f"approve_{uid}"), InlineKeyboardButton("❌ رفض", callback_data=f"reject_{uid}"))
                bot.send_message(ADMIN_ID, f"🔔 طلب جديد:\n👤 {message.from_user.first_name}\n📛 @{uname}\n🆔 {uid}", reply_markup=markup)
        else:
            bot.send_message(message.chat.id, "⏳ يرجى انتظار تفعيل حسابك.")

@bot.message_handler(func=lambda m: m.text == "🎛 لوحة التحكم")
def open_panel(message):
    if is_admin(message.from_user.id):
        bot.send_message(message.chat.id, "🎛 لوحة التحكم الرئيسية:", reply_markup=admin_panel_keyboard())

@bot.callback_query_handler(func=lambda call: call.data.startswith("panel_"))
def handle_panel(call):
    if not is_admin(call.from_user.id): return
    bot.answer_callback_query(call.id)
    
    if call.data == "panel_users":
        users_list = supabase_get("allowed_users", "select=telegram_id,username")
        if not users_list:
            bot.send_message(call.message.chat.id, "📭 لا يوجد مستخدمون.")
        else:
            for u in users_list:
                uid, uname = u['telegram_id'], u.get('username', 'مجهول')
                markup = InlineKeyboardMarkup().add(InlineKeyboardButton("❌ حظر", callback_data=f"ban_{uid}"))
                bot.send_message(call.message.chat.id, f"👤 @{uname}\n🆔 {uid}", reply_markup=markup)
                
    elif call.data == "panel_stats":
        all_orders = supabase_get("orders", "select=status")
        total = len(all_orders) if all_orders else 0
        completed = sum(1 for o in all_orders if o['status'] == 'Completed') if all_orders else 0
        rejected = sum(1 for o in all_orders if o['status'] == 'Rejected') if all_orders else 0
        in_process = sum(1 for o in all_orders if o['status'] == 'In Process') if all_orders else 0
        bot.send_message(call.message.chat.id, f"📊 **إحصائيات:**\n\n👥 مفعّلين: {len(ALLOWED_USERS)}\n📦 الإجمالي: {total}\n✅ ناجحة: {completed}\n❌ مرفوضة: {rejected}\n⏳ قيد المعالجة: {in_process}", parse_mode="Markdown")

    elif call.data == "panel_all_orders":
        orders = supabase_get("orders", "order=created_at.desc&limit=10")
        if not orders:
            bot.send_message(call.message.chat.id, "📭 السجل فارغ.")
            return
        report = "📋 **آخر العمليات:**\n\n"
        for o in orders:
            icon = "✅" if o['status'] == 'Completed' else ("⏳" if o['status'] == 'In Process' else "❌")
            report += f"{icon} الزبون: @{o.get('telegram_user')}\n📦 {o['service_name']}\n🆔 {o['identifier']}\n📊 {o['status']}\n\n"
        bot.send_message(call.message.chat.id, report[:4000])

    elif call.data == "panel_balance":
        p2p = api_post_generic(P2P_CONFIG, {"action": "accountinfo"})
       xxx = api_post_generic(xxx_CONFIG, {"action": "accountinfo"})
        def b(r):
            try: return r["SUCCESS"][0]["AccountInfo"]["credit"]
            except: return "Error"
        bot.send_message(call.message.chat.id, f"💰 أرصدة السيرفر:\n\n🔵 P2P: {b(p2p)} USD\n🟢 xxx: {b(xxx)} USD")

@bot.callback_query_handler(func=lambda call: call.data.startswith(("approve_", "reject_", "ban_")))
def manage_access(call):
    if not is_admin(call.from_user.id): return
    act, uid = call.data.split("_")
    if act == "approve":
        info = PENDING_REQUESTS.get(uid, {})
        add_allowed_user(uid, info.get("username", ""), call.from_user.id)
        bot.send_message(uid, "✅ تم تفعيل حسابك بنجاح!")
        bot.edit_message_text(f"✅ تم تفعيل {uid}", call.message.chat.id, call.message.message_id)
        PENDING_REQUESTS.pop(uid, None)
    elif act == "reject":
        bot.send_message(uid, "❌ نعتذر، تم رفض طلبك.")
        PENDING_REQUESTS.pop(uid, None)
        bot.delete_message(call.message.chat.id, call.message.message_id)
    elif act == "ban":
        remove_allowed_user(uid)
        bot.edit_message_text(f"❌ تم إزالة {uid}", call.message.chat.id, call.message.message_id)

# ================= الطلبات =================
@bot.message_handler(func=lambda m: m.text == "🛒 Place an order")
def start_order(message):
    if not is_authorized(message.from_user.id): return
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("📱 IMEI Service", callback_data="type_imei"), InlineKeyboardButton("🖥 Server Service", callback_data="type_server"))
    bot.send_message(message.chat.id, "📦 اختر النوع:", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("type_"))
def sel_type(call):
    k = call.data.split("_")[1]
    markup = InlineKeyboardMarkup()
    for sid, info in P2P_SERVICES.items():
        if (k == "imei" and info["type"] == "imei") or (k == "server" and info["type"] == "imei_custom"):
            markup.add(InlineKeyboardButton(info["name"], callback_data=f"sel_{sid}_p2p_{k}"))
    for sid, info in xxx_SERVICES.items():
        if k == "imei" and info["type"] == "imei":
            markup.add(InlineKeyboardButton(info["name"], callback_data=f"sel_{sid}_xxx_{k}"))
    bot.edit_message_text("اختر الخدمة:", call.message.chat.id, call.message.message_id, reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("sel_"))
def sel_svc(call):
    _, sid, api, kind = call.data.split("_")
    svc = P2P_SERVICES.get(sid) if api == "p2p" else xxx_SERVICES.get(sid)
    user_states[call.message.chat.id] = {
        "sid": sid, "api": api, "name": svc["name"], "type": svc["type"], 
        "info": svc, "step": "id", "kind": kind, "uname": call.from_user.username or call.from_user.first_name
    }
    bot.send_message(call.message.chat.id, f"✅ {svc['name']}\n\n✏️ أرسل المعرف (IMEI/Email):")

@bot.message_handler(func=lambda m: m.chat.id in user_states)
def order_inputs(message):
    state = user_states[message.chat.id]
    if state["step"] == "id":
        state["id_val"] = message.text.strip()
        if "qnt_min" in state["info"]:
            state["step"] = "qnt"
            bot.send_message(message.chat.id, "🔢 أدخل الكمية:")
        else: finalize_order(message.chat.id)
    elif state["step"] == "qnt":
        state["qnt_val"] = message.text.strip()
        finalize_order(message.chat.id)

def finalize_order(chat_id):
    state = user_states.pop(chat_id)
    bot.send_message(chat_id, "⏳ جاري الإرسال...")
    
    payload = {"action": "placeimeiorder", "parameters[ID]": state["sid"], "parameters[IMEI]": state["id_val"]}
    if "qnt_val" in state: payload["parameters[QNT]"] = state["qnt_val"]
    if state["type"] == "imei_custom": payload[f"parameters[{state['info']['id_label']}]"] = state["id_val"]
    
    config = P2P_CONFIG if state["api"] == "p2p" else xxx_CONFIG
    res = api_post_generic(config, payload)
    
    if "SUCCESS" in res:
        ref = str(res["SUCCESS"][0].get("REFERENCEID"))
        bot.send_message(chat_id, f"✅ تم الإرسال! مرجع: {ref}")
        supabase_post("orders", {
            "telegram_id": str(chat_id), "telegram_user": state["uname"],
            "service_type": "IMEI" if state["kind"] == "imei" else "Server",
            "service_name": state["name"], "identifier": state["id_val"],
            "reference_id": ref, "status": "In Process", "api_source": state["api"]
        })
        with orders_lock: pending_orders[ref] = {"chat_id": chat_id, "api": state["api"]}
        if ADMIN_ID: bot.send_message(ADMIN_ID, f"🔔 طلب جديد: {state['name']}\n👤 @{state['uname']}")
    else:
        err = res.get("ERROR", [{"MESSAGE": "Unknown"}])[0]["MESSAGE"]
        bot.send_message(chat_id, f"❌ خطأ: {err}")

# ================= المراقبة (Poller) =================
def poller():
    while True:
        time.sleep(CHECK_INTERVAL)
        with orders_lock: items = list(pending_orders.items())
        for ref, info in items:
            config = P2P_CONFIG if info["api"] == "p2p" else xxx_CONFIG
            res = api_post_generic(config, {"action": "getimeiorder", "parameters[ID]": ref})
            if "SUCCESS" in res:
                d = res["SUCCESS"][0]
                s = str(d.get("STATUS", "")).lower()
                clean_res = clean_result(extract_result(d))
                if s in ["4", "completed", "success", "delivered", "available"]:
                    bot.send_message(info["chat_id"], f"🔔 نتيجة طلبك (Ref: {ref}):\n\n{clean_res}")
                    supabase_patch("orders", {"status": "Completed", "result": clean_res}, f"reference_id=eq.{ref}")
                    with orders_lock: pending_orders.pop(ref, None)
                elif s in ["3", "rejected", "refunded", "canceled", "failed"]:
                    reason = clean_res if clean_res else "نعتذر، تم رفض الطلب."
                    bot.send_message(info["chat_id"], f"❌ رفض الطلب (Ref: {ref}):\n\n📝 السبب: {reason}")
                    supabase_patch("orders", {"status": "Rejected", "result": reason}, f"reference_id=eq.{ref}")
                    with orders_lock: pending_orders.pop(ref, None)

if __name__ == "__main__":
    print("🤖 بدأت عملية تشغيل البوت...")
    load_bot_data()
    threading.Thread(target=poller, daemon=True).start()
    try:
        bot.infinity_polling(timeout=60, long_polling_timeout=60)
    except Exception as e:
        print(f"🚨 Bot Polling Crash: {e}")
        time.sleep(5)

