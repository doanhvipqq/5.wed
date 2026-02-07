# ==========================================
# ĐĂNG NHẬP - Xử lý đăng nhập Instagram
# ==========================================

import requests
import time
import json
from .cauhinh import DEFAULT_USER_AGENT

class InstagramLogin:
    def __init__(self):
        self.session = requests.Session()
        self.headers = {
            'User-Agent': DEFAULT_USER_AGENT,
            'Accept': '*/*',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'X-IG-App-ID': '936619743392459',
            'X-ASBD-ID': '198387',
            'X-IG-WWW-Claim': '0',
            'Origin': 'https://www.instagram.com',
            'Referer': 'https://www.instagram.com/accounts/login/',
        }
        self.session.headers.update(self.headers)

    def login(self, username, password, proxy=None):
        if proxy:
            self.session.proxies.update(proxy)
            
        try:
            # 1. Lấy CSRF token
            r = self.session.get('https://www.instagram.com/accounts/login/', timeout=10)
            csrf = self.session.cookies.get('csrftoken')
            
            if not csrf:
                 pass
            
            self.session.headers.update({'X-Csrftoken': csrf or 'missing'})
            
            # 2. Gửi request đăng nhập
            timestamp = int(time.time())
            payload = {
                'username': username,
                'enc_password': f'#PWD_INSTAGRAM_BROWSER:0:{timestamp}:{password}',
                'queryParams': {},
                'optIntoOneTap': 'false'
            }
            
            r_login = self.session.post(
                'https://www.instagram.com/api/v1/web/accounts/login/ajax/',
                data=payload,
                timeout=15
            )
            data = r_login.json()
            
            if data.get('authenticated'):
                 cookies = "; ".join([f"{k}={v}" for k, v in self.session.cookies.items()])
                 return {"status": "success", "cookies": cookies}
                 
            if data.get('two_factor_required'):
                return {"status": "2fa_required", "data": data.get('two_factor_info', {})}
                
            msg = data.get('message') or "Đăng nhập thất bại"
            if "checkpoint_required" in data:
                return {"status": "checkpoint", "message": f"Checkpoint!: {data.get('checkpoint_url')}", "data": data}
                
            return {"status": "fail", "message": msg}
            
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def submit_2fa(self, identifier, code, method='sms'):
        """Gửi mã xác thực 2FA"""
        payload = {
            'verificationCode': code,
            'identifier': identifier
        }
        
        try:
            r = self.session.post(
                'https://www.instagram.com/api/v1/web/accounts/login/ajax/two_factor/',
                data=payload,
                timeout=15
            )
            data = r.json()
            
            if data.get('authenticated'):
                 cookies = "; ".join([f"{k}={v}" for k, v in self.session.cookies.items()])
                 return {"status": "success", "cookies": cookies}
                 
            return {"status": "fail", "message": data.get('message', 'Mã 2FA không hợp lệ')}
            
        except Exception as e:
             return {"status": "error", "message": str(e)}
