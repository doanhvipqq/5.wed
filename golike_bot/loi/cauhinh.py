# ==========================================
# CẤU HÌNH CHUNG - Merged từ constants.py và config.py
# ==========================================

import json
import os

# ==========================================
# API URLs - Golike
# ==========================================
API_BASE = "https://gateway.golike.net/api"
INSTAGRAM_ACCOUNT_URL = f"{API_BASE}/instagram-account"
GET_JOBS_URL = f"{API_BASE}/advertising/publishers/instagram/jobs"
COMPLETE_JOBS_URL = f"{API_BASE}/advertising/publishers/instagram/complete-jobs"
REPORT_URL = f"{API_BASE}/report/send"
SKIP_JOBS_URL = f"{API_BASE}/advertising/publishers/instagram/skip-jobs"
INSTAGRAM_ADD_URL = f"{API_BASE}/instagram-account/add"
VERIFY_ACCOUNT_URL = f"{API_BASE}/instagram-account/verify-account"

# ==========================================
# User Agent
# ==========================================
DEFAULT_USER_AGENT = 'Mozilla/50 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'
GLOBAL_USER_AGENT = DEFAULT_USER_AGENT

# ==========================================
# Thời gian khóa tài khoản (giây)
# ==========================================
LOCK_TIME_SECONDS = 600  # 10 phút tạm ngưng khi tài khoản IG bị block/login required

# ==========================================
# Đường dẫn file dữ liệu
# ==========================================
AUTHORIZATION_FILE = "data/Authorization.txt"
LOGIN_INFO_FILE = "data/login_IG.json"
USER_AGENT_FILE = "data/user_agent.txt"
CONFIG_FILE = "data/config.json"
TWO_FA_KEYS_FILE = "data/2fa_keys.json"
PROXY_MAPPING_FILE = "data/proxy_mapping.json"
TELEGRAM_CONFIG_FILE = "config.json"

# ==========================================
# Hàm tải/lưu Telegram Token
# ==========================================
def load_telegram_token():
    if os.path.exists(TELEGRAM_CONFIG_FILE):
        try:
            with open(TELEGRAM_CONFIG_FILE, 'r', encoding='utf-8') as f:
                config = json.load(f)
                return config.get("TELEGRAM_BOT_TOKEN")
        except:
            pass
    return None

def save_telegram_token(token):
    try:
        with open(TELEGRAM_CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump({"TELEGRAM_BOT_TOKEN": token}, f, indent=4)
    except:
        pass
