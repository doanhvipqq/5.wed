import logging
import multiprocessing
import sys
import json
import os
import asyncio
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove, BotCommand
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ConversationHandler,
    ContextTypes,
)

# Import Lõi Modules
from loi.xulyjob import run_worker
from loi.golike import GolikeAPI
from loi.dangnhap import InstagramLogin
from loi.cauhinh import load_telegram_token, save_telegram_token, TELEGRAM_CONFIG_FILE
from loi.tienich import safe_dict_check, get_account_proxy, format_proxy_for_requests, assign_proxy_to_account, parse_proxy_string, validate_proxy

# Cấu hình Logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# Định nghĩa các trạng thái cho ConversationHandler
(
    AUTH,
    SELECT_ACC,
    INPUT_COOKIES,
    INPUT_PASSWORD,
    INPUT_2FA,
    CONF_ADD_GOLIKE,
    INPUT_PROXY_CHOICE,
    INPUT_PROXY,
    CONF_DELAY,
    CONF_LAN2,
    CONF_FAIL,
    CONF_SUCCESS,
    CONF_RATIO,
    CONF_TYPE,
    CONF_AUTOBOT,
    CONF_SCROLL,
) = range(16)

# Dictionary lưu trữ các process đang chạy: {chat_id: process}
active_workers = {}

def get_cookie_path(username):
    # Check new location
    # Create dir if not exists
    os.makedirs("data/cookies", exist_ok=True)
    path = f"data/cookies/{username}.txt"
    if os.path.exists(path):
        return path
    # Check legacy location
    path = f"cookies_{username}.txt"
    if os.path.exists(path):
        return path
    return None

def save_cookie_file(username, content):
    os.makedirs("data/cookies", exist_ok=True)
    path = f"data/cookies/{username}.txt"
    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)
    return path

def read_file(path):
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return f.read().strip()
    except:
        return None

# --- CÁC HÀM HANDLER CHO BOT ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Bắt đầu hội thoại: Hỏi Authorization."""
    print(f"DEBUG: Nhận lệnh /start từ user {update.effective_user.id}")
    chat_id = update.effective_chat.id
    
    # Kiểm tra xem có đang chạy không
    if chat_id in active_workers and active_workers[chat_id].is_alive():
        await update.message.reply_text(
            "⚠️ Tool đang chạy! Hãy dùng /stop để dừng trước khi cấu hình lại."
        )
        return ConversationHandler.END

    await update.message.reply_text(
        "✨ Xin chào! Hãy cấu hình để chạy Tool (Phiên bản mới).\n\n"
        "👉 <b>Bước 1:</b> Vui lòng nhập <b>Authorization</b> của bạn:",
        parse_mode="HTML"
    )
    return AUTH

async def receive_auth(update: Update, context: ContextTypes.DEFAULT_TYPE):
    auth = update.message.text.strip()
    
    if not auth:
        await update.message.reply_text("❌ Authorization không được để trống. Vui lòng nhập lại.")
        return AUTH
    
    # Check thử Authorization bằng cách gọi API chonacc
    msg = await update.message.reply_text("⏳ Đang kiểm tra Authorization...")
    
    # Sử dụng GolikeAPI mới
    try:
        api = GolikeAPI(auth)
    except Exception as e:
        await msg.edit_text(f"❌ Lỗi khởi tạo API: {e}")
        return AUTH
    
    # Chạy hàm blocking trong thread pool
    loop = asyncio.get_running_loop()
    try:
        result = await loop.run_in_executor(None, api.get_accounts)
    except Exception as e:
        await msg.edit_text(f"❌ Lỗi khi gọi API: {e}")
        return AUTH

    if result.get("status") != 200:
        await msg.edit_text(f"❌ Authorization sai hoặc lỗi API: {result.get('message')}\n\nVui lòng nhập lại Auth đúng:")
        return AUTH

    # Lưu auth và danh sách acc vào context
    context.user_data["auth"] = auth
    context.user_data["raw_accounts"] = result["data"] # Danh sách dict acc
    
    # Hiển thị danh sách acc để chọn
    acc_list_text = "✅ <b>Authorization Hợp Lệ!</b>\n\nDanh sách tài khoản:\n"
    for i, acc in enumerate(result["data"]):
        status = "✅" if acc.get('status') == 1 else "❌"
        acc_list_text += f"{i+1}. {acc['instagram_username']} ({status})\n"
    
    acc_list_text += "\n👉 <b>Bước 2:</b> Nhập STT các tài khoản muốn chạy (VD: 1,3,5) hoặc nhập <b>all</b> để chọn tất cả:"
    
    await msg.edit_text(acc_list_text, parse_mode="HTML")
    return SELECT_ACC

async def receive_accounts(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip().lower()
    raw_accounts = context.user_data.get("raw_accounts", [])
    selected_indices = []

    if text == 'all':
        selected_indices = list(range(len(raw_accounts)))
    else:
        try:
            parts = text.split(',')
            for p in parts:
                if p.strip().isdigit():
                    idx = int(p.strip()) - 1
                    if 0 <= idx < len(raw_accounts):
                        selected_indices.append(idx)
        except ValueError:
            pass

    if not selected_indices:
        await update.message.reply_text("❌ Lựa chọn không hợp lệ. Vui lòng nhập lại (VD: 1,2 hoặc all):")
        return SELECT_ACC
    
    # LỌC VÀ CHUẨN BỊ ACCOUNT DATA
    context.user_data["selected_indices"] = selected_indices
    
    # Tìm các tài khoản thiếu cookies
    missing_cookie_accounts = []
    ready_accounts = []
    
    for idx in selected_indices:
        acc_info = raw_accounts[idx]
        username = acc_info['instagram_username']
        path = get_cookie_path(username)
        
        if path:
            # Đã có cookies
            ready_accounts.append({
                "id": acc_info['id'],
                "username": username,
                "cookies": read_file(path),
                "is_locked": False
            })
        else:
            # Chưa có
            missing_cookie_accounts.append({
                "id": acc_info['id'],
                "username": username
            })
            
    context.user_data["ready_accounts"] = ready_accounts
    context.user_data["missing_cookie_accounts"] = missing_cookie_accounts
    
    if missing_cookie_accounts:
        # Bắt đầu quy trình nhập cookies
        context.user_data["current_missing_index"] = 0
        first_user = missing_cookie_accounts[0]['username']
        await update.message.reply_text(
            f"⚠️ Phát hiện {len(missing_cookie_accounts)} tài khoản chưa có cookies.\n\n"
            f"👉 <b>Chọn cách nhập cho {first_user}:</b>\n"
            f"1. Gõ <b>Cookies</b> trực tiếp\n"
            f"2. Gõ <b>login</b> để đăng nhập Pass\n"
            f"3. Gõ <b>skip</b> để bỏ qua",
            parse_mode="HTML"
        )
        return INPUT_COOKIES
        
    else:
        # Đã đủ cookies, sang bước tiếp theo
        context.user_data["final_accounts"] = ready_accounts 
        return await ask_delay(update, context)

async def receive_cookies_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    missing_list = context.user_data["missing_cookie_accounts"]
    current_idx = context.user_data["current_missing_index"]
    current_acc_info = missing_list[current_idx]
    username = current_acc_info['username']
    
    if text.lower() == 'skip':
        await update.message.reply_text(f"⚠️ Đã bỏ qua {username}.")
        return await advance_to_next_missing(update, context)
        
    if text.lower() == 'login':
        # Switch to password mode
        await update.message.reply_text(
            f"🔐 <b>Đăng nhập cho {username}</b>\n"
            f"👉 Vui lòng nhập <b>Mật khẩu</b>:",
            parse_mode="HTML"
        )
        return INPUT_PASSWORD
        
    # Assume text is cookie
    if "sessionid" not in text:
         await update.message.reply_text("⚠️ Cookies sai. Nhập lại hoặc gõ 'login':")
         return INPUT_COOKIES
         
    # Save cookie
    save_cookie_file(username, text)
    # Update temporary cookies in missing_list for later reference
    context.user_data["missing_cookie_accounts"][current_idx]['cookies'] = text
    
    await update.message.reply_text(
        f"✅ Đã lưu cookies.\n👉 <b>Có muốn thêm {username} vào Golike không? (y/n)</b>\n(Chọn 'y' nếu đây là acc mới chưa add vào Golike)",
        parse_mode="HTML"
    )
    return CONF_ADD_GOLIKE

async def receive_password(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    current_idx = context.user_data["current_missing_index"]
    username = context.user_data["missing_cookie_accounts"][current_idx]['username']
    
    if text.lower() == 'skip':
        await update.message.reply_text(f"⚠️ Đã bỏ qua {username}.")
        return await advance_to_next_missing(update, context) 

    password = text
    # Delete password message for security if possible
    
    msg = await update.message.reply_text("⏳ Đang thử đăng nhập...")
    
    # Initialize Login
    login_client = InstagramLogin()
    context.user_data["login_client"] = login_client # Keep session
    
    # Get proxy if any
    proxy_dict = get_account_proxy(username)
    req_proxy = format_proxy_for_requests(proxy_dict) if proxy_dict else None
    
    loop = asyncio.get_running_loop()
    res = await loop.run_in_executor(None, login_client.login, username, password, req_proxy)
    
    if res['status'] == 'success':
        cookies = res['cookies']
        save_cookie_file(username, cookies)
        context.user_data["missing_cookie_accounts"][current_idx]['cookies'] = cookies
        
        await msg.edit_text(f"✅ Đăng nhập thành công!\n👉 <b>Có muốn thêm {username} vào Golike không? (y/n)</b>", parse_mode="HTML")
        return CONF_ADD_GOLIKE
        
    elif res['status'] == '2fa_required':
        context.user_data["2fa_info"] = res['data']
        # Ask for 2FA
        info = res['data']
        method_str = "SMS" if info.get('sms_two_factor_on') else "App Authenticator"
        if info.get('totp_two_factor_on') and info.get('sms_two_factor_on'):
            method_str = "SMS hoặc App"
            
        await msg.edit_text(
            f"🔐 <b>Yêu cầu xác thực 2FA ({method_str})</b>\n"
            f"👉 Nhập mã xác thực gửi về máy bạn:",
            parse_mode="HTML"
        )
        return INPUT_2FA
        
    elif res['status'] == 'checkpoint':
        await msg.edit_text(
            f"🚨 <b>Checkpoint!</b>\n{res['message']}\n"
            f"👉 Bạn cần vào Web/App Instagram để xác minh.\n"
            f"👉 Sau khi xác minh xong, nhập lại Pass để thử lại.\n"
            f"👉 Hoặc gõ <b>skip</b> để bỏ qua tài khoản này.",
            parse_mode="HTML"
        )
        return INPUT_PASSWORD
        
    else:
        await msg.edit_text(f"❌ Đăng nhập thất bại: {res.get('message')}\n\n👉 Nhập lại Mật khẩu hoặc gõ <b>skip</b> để bỏ qua:", parse_mode="HTML")
        return INPUT_PASSWORD

async def receive_2fa(update: Update, context: ContextTypes.DEFAULT_TYPE):
    code = update.message.text.strip()
    current_idx = context.user_data["current_missing_index"]
    username = context.user_data["missing_cookie_accounts"][current_idx]['username']
    
    msg = await update.message.reply_text("⏳ Đang xác thực 2FA...")
    
    login_client = context.user_data["login_client"]
    info = context.user_data["2fa_info"]
    identifier = info.get('two_factor_identifier') or info.get('two_factor_id')
    
    loop = asyncio.get_running_loop()
    res = await loop.run_in_executor(None, login_client.submit_2fa, identifier, code)
    
    if res['status'] == 'success':
        cookies = res['cookies']
        save_cookie_file(username, cookies)
        context.user_data["missing_cookie_accounts"][current_idx]['cookies'] = cookies
        
        await msg.edit_text(f"✅ 2FA Thành công!\n👉 <b>Có muốn thêm {username} vào Golike không? (y/n)</b>", parse_mode="HTML")
        return CONF_ADD_GOLIKE
    else:
        await msg.edit_text(f"❌ Mã sai: {res.get('message')}\n👉 Nhập lại Mã:", parse_mode="HTML")
        return INPUT_2FA

# NEW HANDLERS

async def receive_add_golike_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    choice = update.message.text.strip().lower()
    current_idx = context.user_data["current_missing_index"]
    acc = context.user_data["missing_cookie_accounts"][current_idx]
    username = acc['username']
    cookies = acc.get('cookies')
    auth = context.user_data["auth"]
    
    if choice == 'y':
        msg = await update.message.reply_text(f"⏳ Đang thêm {username} vào Golike (Follow mồi + API)...")
        
        proxy_dict = get_account_proxy(username)
        api = GolikeAPI(auth)
        
        loop = asyncio.get_running_loop()
        success, message = await loop.run_in_executor(None, api.add_account, username, cookies, proxy_dict)
        
        if success:
            await msg.edit_text(f"✅ {message}")
        else:
            await msg.edit_text(f"⚠️ {message}")
    
    await update.message.reply_text(f"👉 <b>Có muốn cài Proxy cho {username} không? (y/n)</b>", parse_mode="HTML")
    return INPUT_PROXY_CHOICE

async def receive_proxy_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    choice = update.message.text.strip().lower()
    if choice == 'y':
        await update.message.reply_text("👉 <b>Nhập Proxy (IP:Port hoặc IP:Port:User:Pass):</b>", parse_mode="HTML")
        return INPUT_PROXY
    else:
        # Save to ready_accounts
        return await finalize_current_account(update, context)

async def receive_proxy_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    current_idx = context.user_data["current_missing_index"]
    username = context.user_data["missing_cookie_accounts"][current_idx]['username']
    
    proxy_dict = parse_proxy_string(text)
    if not proxy_dict:
        await update.message.reply_text("❌ Định dạng Proxy sai. Nhập lại (VD: 1.2.3.4:8080):")
        return INPUT_PROXY
        
    valid, msg = validate_proxy(proxy_dict)
    if not valid:
        await update.message.reply_text(f"❌ Proxy không hợp lệ: {msg}. Nhập lại:")
        return INPUT_PROXY
        
    assign_proxy_to_account(username, proxy_dict)
    await update.message.reply_text(f"✅ Đã lưu Proxy cho {username}.")
    return await finalize_current_account(update, context)

async def finalize_current_account(update, context):
    current_idx = context.user_data["current_missing_index"]
    acc = context.user_data["missing_cookie_accounts"][current_idx]
    
    context.user_data["ready_accounts"].append({
        "id": acc['id'],
        "username": acc['username'],
        "cookies": acc['cookies'],
        "is_locked": False
    })
    
    return await advance_to_next_missing(update, context)

async def advance_to_next_missing(update, context):
    context.user_data["current_missing_index"] += 1
    idx = context.user_data["current_missing_index"]
    missing = context.user_data["missing_cookie_accounts"]
    
    if idx < len(missing):
        next_user = missing[idx]['username']
        await update.message.reply_text(
            f"👉 <b>Chọn cách nhập cho {next_user}:</b>\n"
            f"1. Gõ <b>Cookies</b> trực tiếp\n"
            f"2. Gõ <b>login</b> để đăng nhập Pass\n"
            f"3. Gõ <b>skip</b> để bỏ qua",
            parse_mode="HTML"
        )
        return INPUT_COOKIES
    else:
        return await ask_delay(update, context)

async def ask_delay(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ready_accounts = context.user_data["ready_accounts"]
    
    # Format lại về final structure
    final_accounts = []
    for acc in ready_accounts:
        final_accounts.append({
            "id": acc['id'],
            "username": acc['username'],
            "cookies": acc['cookies'],
            "fail_count": 0,
            "success_count": 0,
            "is_locked": False, 
            "lock_until": 0 
        })
    
    context.user_data["final_accounts"] = final_accounts
    
    if not final_accounts:
        await update.message.reply_text("❌ Không có tài khoản nào có cookies hợp lệ để chạy. Vui lòng thử lại /start.")
        return ConversationHandler.END

    await update.message.reply_text(
        f"✅ Đã có {len(final_accounts)} tài khoản sẵn sàng.\n\n"
        "👉 <b>Bước 3:</b> Nhập thời gian <b>Delay</b> (giây) giữa các job (VD: 5):",
        parse_mode="HTML"
    )
    return CONF_DELAY

async def receive_delay(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        delay = int(update.message.text.strip())
        if delay < 3:
            await update.message.reply_text("❌ Delay phải >= 3 giây. Nhập lại:")
            return CONF_DELAY
        context.user_data["delay"] = delay
    except ValueError:
        await update.message.reply_text("❌ Vui lòng nhập số nguyên. Nhập lại:")
        return CONF_DELAY

    await update.message.reply_text(
        "👉 <b>Bước 4:</b> Có nhận tiền lần 2 nếu lần 1 thất bại không? (y/n):",
        reply_markup=ReplyKeyboardMarkup([['y', 'n']], one_time_keyboard=True, resize_keyboard=True),
        parse_mode="HTML"
    )
    return CONF_LAN2

async def receive_lan2(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.lower().strip()
    context.user_data["lannhan"] = "y" if text == 'y' else "n"

    await update.message.reply_text(
        "👉 <b>Bước 5:</b> Sau bao nhiêu job thất bại thì đổi tài khoản? (VD: 5):",
        reply_markup=ReplyKeyboardRemove(),
        parse_mode="HTML"
    )
    return CONF_FAIL

async def receive_fail_limit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        limit = int(update.message.text.strip())
        if limit < 1: raise ValueError
        context.user_data["doiacc"] = limit
    except ValueError:
        await update.message.reply_text("❌ Nhập số nguyên >= 1. Nhập lại:")
        return CONF_FAIL

    await update.message.reply_text(
        "👉 <b>Bước 6:</b> Làm bao nhiêu job thành công thì đổi tài khoản? (VD: 10):",
        parse_mode="HTML"
    )
    return CONF_SUCCESS

async def receive_success_limit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        limit = int(update.message.text.strip())
        if limit < 1: raise ValueError
        context.user_data["job_limit"] = limit
    except ValueError:
        await update.message.reply_text("❌ Nhập số nguyên >= 1. Nhập lại:")
        return CONF_SUCCESS

    await update.message.reply_text(
        "👉 <b>Bước 7:</b> Nhập tỉ lệ Like,Follow (VD: 1,1):",
        parse_mode="HTML"
    )
    return CONF_RATIO

async def receive_ratio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    try:
        parts = [int(p) for p in text.split(',')]
        if len(parts) != 2: raise ValueError
        context.user_data["job_ratio_str"] = text
    except ValueError:
        await update.message.reply_text("❌ Định dạng sai (VD: 1,1). Nhập lại:")
        return CONF_RATIO

    await update.message.reply_text(
        "👉 <b>Bước 8:</b> Chọn chế độ làm việc:\n1 = Chỉ Follow\n2 = Chỉ Like\n12 = Cả hai",
        reply_markup=ReplyKeyboardMarkup([['1', '2', '12']], one_time_keyboard=True, resize_keyboard=True),
        parse_mode="HTML"
    )
    return CONF_TYPE

async def receive_type(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if text not in ['1', '2', '12']:
        await update.message.reply_text("❌ Chọn 1, 2 hoặc 12. Chọn lại:")
        return CONF_TYPE
    
    lam = []
    mode_name = ""
    if text == '1':
        lam = ["follow"]
        mode_name = "Chỉ Follow"
    elif text == '2':
        lam = ["like"]
        mode_name = "Chỉ Like"
    else:
        lam = ["follow", "like"]
        mode_name = "Like & Follow"
    
    context.user_data["lam"] = lam
    context.user_data["chedo_job_name"] = mode_name

    await update.message.reply_text(
        "👉 <b>Bước 9:</b> Bật AI AutoBot (lướt newsfeed để giống người)? (y/n):",
        reply_markup=ReplyKeyboardMarkup([['y', 'n']], one_time_keyboard=True, resize_keyboard=True),
        parse_mode="HTML"
    )
    return CONF_AUTOBOT

async def receive_autobot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.lower().strip()
    is_auto = (text == 'y')
    context.user_data["ai_autobot"] = is_auto
    
    if is_auto:
        await update.message.reply_text(
            "👉 <b>Bước 10:</b> Thời gian lướt newsfeed (giây)? (VD: 10):",
            reply_markup=ReplyKeyboardRemove(),
            parse_mode="HTML"
        )
        return CONF_SCROLL
    else:
        context.user_data["scroll_duration"] = 0
        return await start_execution(update, context)

async def receive_scroll(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        dur = int(update.message.text.strip())
        context.user_data["scroll_duration"] = dur
    except ValueError:
        await update.message.reply_text("❌ Nhập số nguyên. Nhập lại:")
        return CONF_SCROLL
    
    return await start_execution(update, context)

async def start_execution(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """KHỞI ĐỘNG PROCESS CHẠY TOOL."""
    chat_id = update.effective_chat.id
    data = context.user_data

    # Config dict
    config = {
        'delay': data['delay'],
        'lannhan': data['lannhan'],
        'doiacc': data['doiacc'],
        'job_limit': data['job_limit'],
        'job_ratio_str': data['job_ratio_str'],
        'lam': data['lam'],
        'ai_autobot': data['ai_autobot'],
        'scroll_duration': data['scroll_duration']
    }
    
    final_accounts = data["final_accounts"]
    auth = data["auth"]

    # Stop old process if exists
    if chat_id in active_workers and active_workers[chat_id].is_alive():
        active_workers[chat_id].terminate()
    
    # Start new process using core.worker
    bot_token = application.bot.token 
    
    p = multiprocessing.Process(
        target=run_worker,
        args=(config, final_accounts, auth, bot_token, chat_id)
    )
    p.daemon = True
    p.start()
    
    active_workers[chat_id] = p
    
    await update.message.reply_text(
        f"✅ <b>CẤU HÌNH HOÀN TẤT!</b>\n"
        f"🚀 Tool đang chạy cho {len(final_accounts)} tài khoản...\n"
        f"🎯 Chế độ: {data['chedo_job_name']}",
        parse_mode="HTML",
        reply_markup=ReplyKeyboardRemove()
    )
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "⛔ Đã hủy cấu hình.", reply_markup=ReplyKeyboardRemove()
    )
    return ConversationHandler.END

async def stop_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if chat_id in active_workers and active_workers[chat_id].is_alive():
        active_workers[chat_id].terminate()
        del active_workers[chat_id]
        await update.message.reply_text("🛑 <b>ĐÃ DỪNG TOOL!</b>", parse_mode="HTML")
    else:
        await update.message.reply_text("⚠️ Tool hiện không chạy.")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📖 <b>HƯỚNG DẪN SỬ DỤNG</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "<b>🔹 Các lệnh có sẵn:</b>\n"
        "/start - Bắt đầu cấu hình và chạy Tool\n"
        "/stop - Dừng Tool đang chạy\n"
        "/help - Xem hướng dẫn này\n"
        "/cancel - Hủy cấu hình hiện tại\n\n"
        "<b>🔹 Các bước cấu hình:</b>\n"
        "1️⃣ Nhập Authorization từ Golike\n"
        "2️⃣ Chọn tài khoản muốn chạy\n"
        "3️⃣ Nhập Cookies/Đăng nhập\n"
        "4️⃣ Cấu hình Delay, số job...\n"
        "5️⃣ Tool sẽ tự động chạy\n\n"
        "<b>🔹 Mẹo:</b>\n"
        "• Delay nên >= 5s để tránh bị khóa\n"
        "• Nên cài Proxy cho mỗi acc\n"
        "• Kiểm tra /stop trước khi /start lại",
        parse_mode="HTML"
    )

application = None

async def post_init(application: Application):
    # Đăng ký menu lệnh gợi ý
    commands = [
        BotCommand("start", "🚀 Bắt đầu cấu hình và chạy Tool"),
        BotCommand("stop", "🛑 Dừng Tool đang chạy"),
        BotCommand("help", "❓ Xem hướng dẫn sử dụng"),
        BotCommand("cancel", "⛔ Hủy cấu hình hiện tại"),
    ]
    await application.bot.set_my_commands(commands)
    
    print(f"✅ Bot đã kết nối thành công!")
    me = await application.bot.get_me()
    print(f"ℹ️ Bot Info: ID={me.id}, Username=@{me.username}, Name={me.first_name}")
    print("👉 Hãy chat /start với bot để bắt đầu.")

def main():
    if sys.platform.startswith('win'):
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')

    print("--- SERVER TELEGRAM BOT (REFACTORED) ---", flush=True)
    
    TOKEN = load_telegram_token()
    
    if not TOKEN:
        TOKEN = input("Nhập Token Bot của bạn: ").strip()
        save_telegram_token(TOKEN)
        
    if not TOKEN:
        print("❌ Lỗi: Chưa nhập Token!")
        return

    # XÂY DỰNG APP
    global application
    application = Application.builder().token(TOKEN).post_init(post_init).build()

    # 3. ĐỊNH NGHĨA CONVERSATION
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            AUTH: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_auth)],
            SELECT_ACC: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_accounts)],
            INPUT_COOKIES: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_cookies_input)],
            INPUT_PASSWORD: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_password)],
            INPUT_2FA: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_2fa)],
            CONF_ADD_GOLIKE: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_add_golike_choice)],
            INPUT_PROXY_CHOICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_proxy_choice)],
            INPUT_PROXY: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_proxy_input)],
            CONF_DELAY: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_delay)],
            CONF_LAN2: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_lan2)],
            CONF_FAIL: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_fail_limit)],
            CONF_SUCCESS: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_success_limit)],
            CONF_RATIO: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_ratio)],
            CONF_TYPE: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_type)],
            CONF_AUTOBOT: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_autobot)],
            CONF_SCROLL: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_scroll)],
        },
        fallbacks=[CommandHandler("cancel", cancel), CommandHandler("stop", stop_command)],
    )

    application.add_handler(conv_handler)
    application.add_handler(CommandHandler("stop", stop_command))
    application.add_handler(CommandHandler("help", help_command))

    print("✅ Bot đang chạy... Nhấn Ctrl+C để dừng.")
    application.run_polling()

if __name__ == "__main__":
    multiprocessing.freeze_support()
    main()
