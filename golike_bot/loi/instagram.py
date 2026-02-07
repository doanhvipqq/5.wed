# ==========================================
# INSTAGRAM - Xử lý tương tác với Instagram
# ==========================================

import requests
import json
import time
from .tienich import format_proxy_for_requests
from .cauhinh import DEFAULT_USER_AGENT, LOCK_TIME_SECONDS

def extract_csrftoken(cookies_str):
    """Trích xuất csrftoken từ chuỗi cookies."""
    for cookie in cookies_str.split(';'):
        if 'csrftoken=' in cookie.strip():
            return cookie.split('=')[1].strip()
    return None

def get_cookie_string(s: requests.Session):
    """Chuyển đối tượng CookieJar thành chuỗi cookies."""
    return "; ".join([f"{k}={v}" for k, v in s.cookies.items()])

def get_ig_headers(cookies: str, referer: str = "https://www.instagram.com/"):
    """Tạo headers cho API Instagram."""
    token = extract_csrftoken(cookies)
    
    IG_HEADERS = {
        'authority': 'i.instagram.com',
        'accept': '*/*',
        'accept-language': 'vi,en-US;q=0.9,en;q=0.8',
        'content-type': 'application/x-www-form-urlencoded',
        'cookie': cookies,
        'origin': 'https://www.instagram.com',
        'referer': referer,
        'user-agent': DEFAULT_USER_AGENT, 
        'x-csrftoken': token if token else '',
        'x-ig-app-id': '936619743392459',
        'x-instagram-ajax': '1006309104',
        'sec-fetch-dest': 'empty',
        'sec-fetch-mode': 'cors',
        'sec-fetch-site': 'same-site',
    }
    return IG_HEADERS

class InstagramClient:
    @staticmethod
    def handle_follow_job(account_info: dict, object_id: str, proxy_dict=None):
        """
        Thực hiện Follow
        Returns: (success: bool, new_cookies: str, result_info: dict)
        """
        cookies = account_info['cookies']
        username = account_info['username']
        
        proxies = format_proxy_for_requests(proxy_dict) if proxy_dict else None
        
        headers = get_ig_headers(cookies)
        url = f"https://i.instagram.com/api/v1/web/friendships/{object_id}/follow/"
        
        session = requests.Session()
        if proxies:
            session.proxies.update(proxies)
        
        result_info = {'locked': False, 'message': ''}
        
        try:
            for c in cookies.split('; '):
                if '=' in c:
                    name, value = c.split('=', 1)
                    session.cookies.set(name, value)
                    
            response = session.post(url, headers=headers, data=None, timeout=10) 
            text = response.text
            
            # Kiểm tra khóa / chặn / checkpoint
            lower_text = text.lower()
            if ('login_required' in lower_text or 
                'checkpoint_required' in lower_text or 
                'challenge_required' in lower_text or 
                'feedback_required' in lower_text or
                'sentry_block' in lower_text or
                response.status_code == 403):
                
                msg = "Cần đăng nhập lại / Bị chặn"
                if 'checkpoint_required' in lower_text: msg = "Yêu cầu xác minh (Vào Web để verify)"
                elif 'challenge_required' in lower_text: msg = "Yêu cầu xác thực Challenge"
                elif 'feedback_required' in lower_text: msg = "Hành động bị chặn (Feedback Required)"
                
                return False, cookies, {
                     'locked': True, 
                     'message': f"Follow thất bại: {msg} ({username})"
                 }

            try:
                response_json = response.json()
            except json.JSONDecodeError:
                return False, cookies, {
                    'locked': False,
                    'message': f"Follow thất bại: Lỗi phản hồi không phải JSON ({response.status_code})."
                }
            
            if response_json.get('status') == 'ok':
                new_cookies = get_cookie_string(session)
                return True, new_cookies, {'locked': False, 'message': "Thành công"}
            else:
                return False, cookies, {
                    'locked': False,
                    'message': f"Follow thất bại: {text[:100]}..."
                }

        except requests.exceptions.TooManyRedirects:
            return False, cookies, {
                'locked': True,
                'message': f"Follow thất bại: Tài khoản {username} bị lỗi Redirects (>30). Cần cập nhật Cookies."
            }
        except Exception as e:
            return False, cookies, {
                'locked': False,
                'message': f"Lỗi nghiêm trọng khi Follow: {e}"
            }

    @staticmethod
    def handle_like_job(account_info: dict, media_id: str, link: str, proxy_dict=None):
        """Thực hiện Like"""
        cookies = account_info['cookies']
        username = account_info['username']
        
        proxies = format_proxy_for_requests(proxy_dict) if proxy_dict else None
        
        headers = get_ig_headers(cookies, referer=link)
        headers['authority'] = 'www.instagram.com'
        headers['x-ig-app-id'] = '936619743392459'
        
        url = f"https://www.instagram.com/web/likes/{media_id}/like/"
        
        session = requests.Session()
        if proxies:
            session.proxies.update(proxies)
            
        try:
            for c in cookies.split('; '):
                if '=' in c:
                    name, value = c.split('=', 1)
                    session.cookies.set(name, value)
                    
            response = session.post(url, headers=headers, data=None, timeout=10) 
            text = response.text
            lower_text = text.lower()

            if ('login_required' in lower_text or 
                'checkpoint_required' in lower_text or 
                'challenge_required' in lower_text or 
                'feedback_required' in lower_text or
                'sentry_block' in lower_text or
                response.status_code == 403):
                
                msg = "Cần đăng nhập lại / Bị chặn"
                if 'checkpoint_required' in lower_text: msg = "Yêu cầu xác minh (Vào Web để verify)"
                elif 'challenge_required' in lower_text: msg = "Yêu cầu xác thực Challenge"
                elif 'feedback_required' in lower_text: msg = "Hành động bị chặn (Feedback Required)"
                
                return False, cookies, {
                     'locked': True, 
                     'message': f"Like thất bại: {msg} ({username})"
                 }
            
            try:
                response_json = response.json()
            except json.JSONDecodeError:
                response_json = {}
                
            if response.status_code == 200 and response_json.get('status') == 'ok':
                new_cookies = get_cookie_string(session)
                return True, new_cookies, {'locked': False, 'message': "Thành công"}
            elif response.status_code == 400 and 'Sorry, this photo has been deleted' in text:
                return False, cookies, {'locked': False, 'message': "ẢNH ĐÃ BỊ XÓA"}
            else:
                return False, cookies, {
                    'locked': False,
                    'message': f"LỖI (Like): Mã {response.status_code}, Phản hồi: {text[:100]}..."
                }

        except requests.exceptions.TooManyRedirects:
             return False, cookies, {
                'locked': True,
                'message': f"Like thất bại: Tài khoản {username} bị lỗi Redirects (>30)."
            }
        except Exception as e:
            return False, cookies, {
                'locked': False,
                'message': f"CÓ LỖI XẢY RA!!! (Network/Unknown): {e}"
            }
