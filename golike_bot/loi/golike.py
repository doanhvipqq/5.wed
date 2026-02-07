# ==========================================
# GOLIKE API - Kết nối với Golike
# ==========================================

import requests
import json
import cloudscraper
from .cauhinh import (
    API_BASE,
    INSTAGRAM_ACCOUNT_URL,
    GET_JOBS_URL,
    COMPLETE_JOBS_URL,
    REPORT_URL,
    SKIP_JOBS_URL,
    INSTAGRAM_ADD_URL,
    DEFAULT_USER_AGENT,
    GLOBAL_USER_AGENT
)
from .tienich import format_proxy_for_requests

def get_base_headers(authorization: str = None):
    """Trả về headers chuẩn cho API GoLike."""
    headers = {
        'Accept-Language': 'vi,en-US;q=0.9,en;q=0.8',
        'Referer': 'https://app.golike.net/',
        'Sec-Ch-Ua': '"Not A(Brand";v="99", "Google Chrome";v="121", "Chromium";v="121"',
        'Sec-Ch-ua-Mobile': '?0',
        'Sec-Ch-Ua-Platform': "Windows",
        'Sec-Fetch-Dest': 'empty',
        'Sec-Fetch-Mode': 'cors',
        'Sec-Fetch-Site': 'same-site',
        'T': 'VFZSak1FMTZZM3BOZWtFd1RtYzlQUT09',
        'User-Agent': GLOBAL_USER_AGENT, 
        'Content-Type': 'application/json;charset=utf-8'
    }
    if authorization:
        headers['Authorization'] = authorization
    return headers

class GolikeAPI:
    def __init__(self, authorization):
        self.authorization = authorization
        self.headers = {
            'Authorization': authorization,
            'T': 'VFZSak1FMTZZM3BOZWtFd1RtYzlQUT09',
            'User-Agent': GLOBAL_USER_AGENT,
            'Content-Type': 'application/json'
        }
        self.scraper = None  # Lazy init

    def get_scraper(self):
        if not self.scraper:
            self.scraper = cloudscraper.create_scraper()
        return self.scraper

    def get_accounts(self):
        """Lấy danh sách tài khoản từ Golike"""
        headers = get_base_headers(self.authorization)
        try:
            response = requests.get(INSTAGRAM_ACCOUNT_URL, headers=headers, timeout=10)
            
            try:
                return response.json()
            except json.JSONDecodeError:
                return {"status": 500, "message": "Lỗi API", "detail": f"Dữ liệu trả về không phải JSON: {response.text[:50]}..."}
                
        except requests.exceptions.RequestException as e:
            return {"status": 500, "message": f"Lỗi mạng: {e}"}
        except Exception as e:
            return {"status": 500, "message": f"Lỗi không xác định: {e}"}

    def get_job(self, account_id):
        """Lấy job mới cho tài khoản"""
        headers = get_base_headers(self.authorization)
        params = {
            'instagram_account_id': account_id,
            'data': 'null'
        }
        try:
            response = requests.get(GET_JOBS_URL, headers=headers, params=params, timeout=10)
            
            if response.status_code == 200:
                try:
                    return response.json()
                except json.JSONDecodeError:
                    return {"status": 500, "message": "Lỗi API: JSON không hợp lệ", "raw_response": response.text}
            elif response.status_code == 400:
                try:
                    return response.json()
                except json.JSONDecodeError:
                    return {"status": 400, "message": "Lỗi tài khoản", "detail": response.text[:50]}
            else:
                return {"status": response.status_code, "message": f"Lỗi HTTP: {response.status_code}"}
                
        except requests.exceptions.RequestException as e:
            return {"status": 500, "message": f"Lỗi mạng: {e}"}
        except Exception as e:
            return {"status": 500, "message": f"Lỗi không xác định: {e}"}

    def complete_job(self, ads_id, account_id):
        """Hoàn thành job"""
        headers = get_base_headers(self.authorization)
        data = {
            'instagram_users_advertising_id': ads_id,
            'instagram_account_id': account_id,
            'async': True,
            'data': None
        }
        
        try:
            response = requests.post(COMPLETE_JOBS_URL, headers=headers, json=data, timeout=10, verify=True) 
            
            if response.status_code == 200:
                try:
                    return response.json()
                except json.JSONDecodeError:
                    return {"status": 500, "error": "Lỗi giải mã JSON"}
            else:
                try:
                    return response.json()
                except json.JSONDecodeError:
                    return {"status": response.status_code, "error": f"Lỗi HTTP {response.status_code}"}

        except requests.exceptions.RequestException as e:
            return {'error': f'Không thể kết nối: {e}', 'status': 500} 
        except Exception as e:
            return {'error': f'Lỗi không xác định: {e}', 'status': 500}

    def report_job(self, ads_id, object_id, account_id, job_type):
        """Báo cáo job đã làm"""
        headers = get_base_headers(self.authorization)
        
        data1 = {
            'description': 'Tôi đã làm Job này rồi',
            'users_advertising_id': ads_id,
            'type': 'ads',
            'provider': 'instagram',
            'fb_id': account_id,
            'error_type': 6
        }
        try:
            requests.post(REPORT_URL, headers=headers, json=data1, timeout=5)
        except requests.exceptions.RequestException:
            pass

        return self.skip_job(ads_id, object_id, account_id, job_type)

    def skip_job(self, ads_id, object_id, account_id, job_type):
        """Bỏ qua job"""
        headers = get_base_headers(self.authorization)
        data2 = {
            'ads_id': ads_id,
            'object_id': object_id,
            'account_id': account_id,
            'type': job_type
        }
        try:
            response = requests.post(SKIP_JOBS_URL, headers=headers, json=data2, timeout=10)
            
            try:
                return response.json()
            except json.JSONDecodeError:
                return {"status": 500, "message": f"Lỗi giải mã JSON: {response.text[:50]}..."}
                
        except requests.exceptions.RequestException as e:
            return {"status": 500, "message": f"Lỗi mạng: {e}"}

    def add_account(self, username, cookies, proxy_dict=None):
        """Thêm tài khoản vào Golike: Follow -> Add API"""
        print(f"[Golike] Đang follow user mồi cho {username}...")
        session = requests.Session()
        if proxy_dict:
            proxies = format_proxy_for_requests(proxy_dict)
            if proxies:
                session.proxies.update(proxies)
            
        # Parse cookies
        for c in cookies.split('; '):
            if '=' in c:
                name, value = c.split('=', 1)
                session.cookies.set(name, value)

        # Get CSRF
        csrf = session.cookies.get('csrftoken')
        try:
             import re
             if not csrf:
                match = re.search(r'csrftoken=([^;]+)', cookies)
                if match: csrf = match.group(1)
        except ImportError:
             pass
        
        if not csrf:
             return False, "Không tìm thấy CSRF token"
             
        target_id = "55607669225" 
        
        follow_url = f"https://www.instagram.com/web/friendships/{target_id}/follow/"
        headers_ig = {
            'User-Agent': GLOBAL_USER_AGENT,
            'X-Csrftoken': csrf,
            'X-Requested-With': 'XMLHttpRequest',
            'Referer': 'https://www.instagram.com/evansnguyen.0104/'
        }
        
        try:
            r_follow = session.post(follow_url, headers=headers_ig, timeout=10)
            print(f"[Golike] Follow status: {r_follow.status_code}")
        except Exception as e:
            print(f"[Golike] Follow error: {e}")

        # 2. Add to Golike
        print(f"[Golike] Đang gửi yêu cầu thêm tài khoản {username}...")
        data = {
            "instagram_username": username,
            "instagram_users_id": "", 
            "avatar": ""
        }
        
        try:
            scraper = self.get_scraper()
            r_add = scraper.post(INSTAGRAM_ADD_URL, headers=self.headers, json=data, timeout=15)
            
            try:
                main_json = r_add.json()
            except:
                return False, f"Lỗi phản hồi Golike: {r_add.text[:50]}"
                
            if main_json.get('status') == 200:
                return True, "Thêm thành công!"
            else:
                return False, f"Thất bại: {main_json.get('message')}"
                
        except Exception as e:
            return False, f"Lỗi kết nối Golike: {e}"
