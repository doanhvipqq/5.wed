# ==========================================
# TIỆN ÍCH - Các hàm hỗ trợ chung
# ==========================================

import re
import requests
import json
import os
import time
from urllib.parse import urlparse
from .cauhinh import PROXY_MAPPING_FILE

def safe_dict_check(data, context="API"):
    """
    Kiểm tra an toàn. Đảm bảo dữ liệu là dictionary. 
    Nếu không phải, trả về một dictionary lỗi để ngăn chặn crash FATAL ERROR: 'str' object has no attribute 'get'.
    """
    if not data:
         error_message = f"Critical Error: {context} returned empty data. Returning 500."
         return {"status": 500, "message": error_message, "critical_safe_check_fail": True}
         
    if not isinstance(data, dict):
        error_message = f"Critical Error: {context} returned type {type(data)} instead of dict. Raw data: {str(data)[:50]}"
        return {"status": 500, "message": error_message, "critical_safe_check_fail": True}
    return data

# ==================== PROXY VALIDATION ====================

def parse_proxy_string(proxy_str):
    """
    Parse chuỗi proxy thành dictionary.
    Hỗ trợ format:
    - ip:port
    - ip:port:user:pass
    - protocol://ip:port
    - protocol://user:pass@ip:port
    
    Returns:
        dict: {
            'protocol': 'http/https/socks4/socks5',
            'host': 'ip',
            'port': 'port',
            'username': 'user' (optional),
            'password': 'pass' (optional),
            'raw': 'original string'
        }
        None nếu invalid
    """
    proxy_str = proxy_str.strip()
    if not proxy_str:
        return None
    
    result = {
        'protocol': 'http',  # Default
        'host': None,
        'port': None,
        'username': None,
        'password': None,
        'raw': proxy_str
    }
    
    # Pattern 1: protocol://user:pass@ip:port
    pattern1 = r'^(https?|socks4|socks5)://([^:]+):([^@]+)@([^:]+):(\d+)$'
    match = re.match(pattern1, proxy_str, re.IGNORECASE)
    if match:
        result['protocol'] = match.group(1).lower()
        result['username'] = match.group(2)
        result['password'] = match.group(3)
        result['host'] = match.group(4)
        result['port'] = match.group(5)
        return result
    
    # Pattern 2: protocol://ip:port
    pattern2 = r'^(https?|socks4|socks5)://([^:]+):(\d+)$'
    match = re.match(pattern2, proxy_str, re.IGNORECASE)
    if match:
        result['protocol'] = match.group(1).lower()
        result['host'] = match.group(2)
        result['port'] = match.group(3)
        return result
    
    # Pattern 3: ip:port:user:pass
    parts = proxy_str.split(':')
    if len(parts) == 4:
        result['host'] = parts[0]
        result['port'] = parts[1]
        result['username'] = parts[2]
        result['password'] = parts[3]
        return result
    
    # Pattern 4: ip:port
    elif len(parts) == 2:
        result['host'] = parts[0]
        result['port'] = parts[1]
        return result
    
    # Pattern 5: user:pass@ip:port
    elif len(parts) == 3 and '@' in parts[1]:
        auth_host = parts[1].split('@')
        if len(auth_host) == 2:
            result['username'] = parts[0]
            result['password'] = auth_host[0]
            result['host'] = auth_host[1]
            result['port'] = parts[2]
            return result
    
    return None

def validate_ip(ip):
    """Validate IPv4 hoặc IPv6"""
    # IPv4
    ipv4_pattern = r'^(\d{1,3}\.){3}\d{1,3}$'
    if re.match(ipv4_pattern, ip):
        parts = ip.split('.')
        return all(0 <= int(part) <= 255 for part in parts)
    
    # IPv6 (simplified check)
    ipv6_pattern = r'^([0-9a-fA-F]{0,4}:){2,7}[0-9a-fA-F]{0,4}$'
    if re.match(ipv6_pattern, ip):
        return True
    
    # Domain name
    domain_pattern = r'^[a-zA-Z0-9][a-zA-Z0-9-]{0,61}[a-zA-Z0-9]?(\.[a-zA-Z]{2,})+$'
    if re.match(domain_pattern, ip):
        return True
    
    return False

def validate_proxy(proxy_dict):
    """
    Validate proxy dictionary
    Returns: (bool, error_message)
    """
    if not proxy_dict:
        return False, "Proxy dictionary is None"
    
    # Check host
    if not proxy_dict.get('host'):
        return False, "Missing host"
    
    if not validate_ip(proxy_dict['host']):
        return False, f"Invalid IP/domain: {proxy_dict['host']}"
    
    # Check port
    try:
        port = int(proxy_dict['port'])
        if not (1 <= port <= 65535):
            return False, f"Port out of range: {port}"
    except (ValueError, TypeError):
        return False, f"Invalid port: {proxy_dict.get('port')}"
    
    # Check protocol
    valid_protocols = ['http', 'https', 'socks4', 'socks5']
    if proxy_dict['protocol'].lower() not in valid_protocols:
        return False, f"Invalid protocol: {proxy_dict['protocol']}"
    
    return True, "Valid"

def format_proxy_for_requests(proxy_dict):
    """
    Format proxy dictionary thành format cho requests library
    Returns: dict cho requests.Session().proxies
    """
    if not proxy_dict:
        return None
        
    protocol = proxy_dict['protocol']
    host = proxy_dict['host']
    port = proxy_dict['port']
    username = proxy_dict.get('username')
    password = proxy_dict.get('password')
    
    # Build proxy URL
    if username and password:
        proxy_url = f"{protocol}://{username}:{password}@{host}:{port}"
    else:
        proxy_url = f"{protocol}://{host}:{port}"
    
    # Requests expects http and https keys
    proxies = {
        'http': proxy_url,
        'https': proxy_url
    }
    
    return proxies

def check_proxy_live(proxy_dict, test_url="http://httpbin.org/ip", timeout=10):
    """
    Kiểm tra proxy có hoạt động không
    Returns: (bool, response_time_ms, error_message)
    """
    try:
        proxies = format_proxy_for_requests(proxy_dict)
        
        start_time = time.time()
        response = requests.get(
            test_url,
            proxies=proxies,
            timeout=timeout,
            verify=False  # Bỏ qua SSL verification
        )
        end_time = time.time()
        
        response_time_ms = int((end_time - start_time) * 1000)
        
        if response.status_code == 200:
            return True, response_time_ms, "OK"
        else:
            return False, response_time_ms, f"HTTP {response.status_code}"
            
    except requests.exceptions.ProxyError as e:
        return False, 0, f"Proxy Error: {str(e)[:50]}"
    except requests.exceptions.Timeout:
        return False, 0, "Timeout"
    except requests.exceptions.ConnectionError as e:
        return False, 0, f"Connection Error: {str(e)[:50]}"
    except Exception as e:
        return False, 0, f"Unknown Error: {str(e)[:50]}"

# ==================== PROXY MANAGEMENT ====================

def load_proxy_mapping():
    """Tải mapping proxy từ file JSON"""
    try:
        with open(PROXY_MAPPING_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}

def save_proxy_mapping(mapping):
    """Lưu mapping proxy vào file JSON"""
    try:
        os.makedirs(os.path.dirname(PROXY_MAPPING_FILE), exist_ok=True)
        with open(PROXY_MAPPING_FILE, 'w', encoding='utf-8') as f:
            json.dump(mapping, f, indent=4, ensure_ascii=False)
        return True
    except Exception as e:
        print(f"[ERROR] Lỗi lưu proxy mapping: {e}")
        return False

def get_account_proxy(username):
    """Lấy proxy đã được gán cho tài khoản"""
    mapping = load_proxy_mapping()
    return mapping.get(username, None)

def assign_proxy_to_account(username, proxy_dict):
    """Gán proxy cho tài khoản và lưu vào file"""
    mapping = load_proxy_mapping()
    mapping[username] = proxy_dict
    save_proxy_mapping(mapping)
    return True
