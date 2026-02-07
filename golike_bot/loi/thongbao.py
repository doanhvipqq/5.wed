# ==========================================
# THÔNG BÁO - Gửi tin nhắn qua Telegram
# ==========================================

import requests

class TelegramNotifier:
    def __init__(self, token, chat_id):
        self.token = token
        self.chat_id = chat_id

    def send_message(self, message):
        if not self.token or not self.chat_id:
            return False
            
        url = f"https://api.telegram.org/bot{self.token}/sendMessage"
        payload = {
            'chat_id': self.chat_id,
            'parse_mode': 'HTML',
            'text': message
        }
        try:
            response = requests.post(url, data=payload, timeout=15)
            return response.status_code == 200
        except:
            return False
