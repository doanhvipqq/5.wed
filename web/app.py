"""
Bóng X AI - Web Backend
Flask API server tích hợp Cerebras AI
"""

import os
import sys
import json
import re
from pathlib import Path
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from werkzeug.utils import secure_filename

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from cerebras.cloud.sdk import Cerebras
from dotenv import load_dotenv

# Load environment
load_dotenv(Path(__file__).parent.parent / '.env')

app = Flask(__name__, static_folder='.', static_url_path='')
CORS(app)

# ==================== CONFIG ====================
PROFILES_DIR = Path(__file__).parent.parent / 'data' / 'profiles'
DATA_DIR = Path(__file__).parent.parent / 'data'
API_KEYS_FILE = Path(__file__).parent.parent / 'api_keys.json'
UPLOADS_DIR = Path(__file__).parent / 'uploads'
UPLOADS_DIR.mkdir(exist_ok=True)
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp', 'pdf', 'txt', 'doc', 'docx'}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB

# ==================== AI CLIENT ====================
class AIClient:
    def __init__(self):
        self.keys = self.load_keys()
        self.current_key_index = 0
        self.client = None
        self.model_name = "qwen-3-32b"
        self.current_profile = "default"
        self.abbreviations = self.load_abbreviations()
        self.setup_ai()
    
    def load_keys(self):
        keys = []
        try:
            with open(API_KEYS_FILE, "r") as f:
                data = json.load(f)
                keys = data.get("cerebras_api_keys", [])
        except FileNotFoundError:
            print("api_keys.json not found!")
        
        # Also check environment variable
        env_key = os.getenv("CER_API_KEY")
        if env_key and env_key not in keys:
            keys.insert(0, env_key)
        
        return keys
    
    def rotate_key(self):
        if not self.keys:
            return False
        self.current_key_index = (self.current_key_index + 1) % len(self.keys)
        self.setup_ai()
        return True
    
    def load_abbreviations(self):
        try:
            with open(DATA_DIR / 'viettat.json', 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return {}
    
    def normalize_input(self, text):
        if not text:
            return ""
        for abbr, full in self.abbreviations.items():
            pattern = re.compile(r'\b' + re.escape(abbr) + r'\b', re.IGNORECASE)
            text = pattern.sub(full, text)
        return text
    
    def setup_ai(self):
        if not self.keys:
            print("No API Keys available!")
            return
        current_key = self.keys[self.current_key_index]
        try:
            self.client = Cerebras(api_key=current_key)
        except Exception as e:
            print(f"Failed to initialize Cerebras SDK: {e}")
    
    def get_available_profiles(self):
        profiles = []
        if PROFILES_DIR.exists():
            for file in PROFILES_DIR.glob("*.json"):
                try:
                    with open(file, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        profiles.append({
                            "id": file.stem,
                            "name": data.get("name", file.stem),
                            "description": data.get("description", "Không có mô tả")
                        })
                except:
                    pass
        return profiles
    
    def load_profile(self, profile_name):
        profile_path = PROFILES_DIR / f"{profile_name}.json"
        if profile_path.exists():
            try:
                with open(profile_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except:
                pass
        return None
    
    def get_system_prompt(self):
        profile = self.load_profile(self.current_profile)
        if not profile:
            profile = self.load_profile("default")
        if not profile:
            return "Bạn là một trợ lý ảo thân thiện."
        
        rules = "\n".join([f"- {r}" for r in profile.get("rules", [])])
        
        return (
            f"{profile.get('context', '')}\n\n"
            f"Tên: {profile.get('name', 'Chatbot')}\n"
            f"Tính cách: {profile.get('personality', 'Friendly')}\n\n"
            f"Quy tắc:\n{rules}\n\n"
            f"Phong cách: {profile.get('language_style', 'Natural')}\n"
        )
    
    def clean_response(self, text):
        # Remove <think> tags
        cleaned = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL).strip()
        
        # Remove markdown formatting
        cleaned = re.sub(r'\*\*', '', cleaned)
        cleaned = re.sub(r'\*', '', cleaned)
        cleaned = re.sub(r'__', '', cleaned)
        cleaned = re.sub(r'~~', '', cleaned)
        cleaned = re.sub(r'`', '', cleaned)
        
        if not cleaned:
            return "..."
        return cleaned.strip()
    
    def generate_reply(self, user_input, history=""):
        if not self.client:
            self.setup_ai()
            if not self.client:
                raise Exception("No AI client available")
        
        normalized_input = self.normalize_input(user_input)
        full_prompt = f"Chat History:\n{history}\n\nUser: {normalized_input}"
        
        max_retries = len(self.keys) if self.keys else 1
        attempts = 0
        
        while attempts < max_retries:
            try:
                response = self.client.chat.completions.create(
                    model=self.model_name,
                    messages=[
                        {"role": "system", "content": self.get_system_prompt()},
                        {"role": "user", "content": full_prompt}
                    ],
                    temperature=0.9,
                    max_tokens=800
                )
                
                raw_text = response.choices[0].message.content.strip()
                return self.clean_response(raw_text)
                
            except Exception as e:
                error_msg = str(e)
                if "401" in error_msg or "429" in error_msg:
                    if self.rotate_key():
                        attempts += 1
                        continue
                raise e
        
        raise Exception("All API Keys exhausted.")

# Initialize AI Client
ai_client = AIClient()

# ==================== ROUTES ====================

@app.route('/')
def index():
    return send_from_directory('.', 'index.html')

@app.route('/api/chat', methods=['POST'])
def chat():
    try:
        data = request.json
        message = data.get('message', '').strip()
        history = data.get('history', '')
        
        if not message:
            return jsonify({'error': 'No message provided'}), 400
        
        reply = ai_client.generate_reply(message, history)
        return jsonify({'reply': reply})
        
    except Exception as e:
        print(f"Chat error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/profiles', methods=['GET'])
def get_profiles():
    profiles = ai_client.get_available_profiles()
    return jsonify({
        'profiles': profiles,
        'current': ai_client.current_profile
    })

@app.route('/api/profile', methods=['POST'])
def set_profile():
    try:
        data = request.json
        profile_id = data.get('profile', '').lower()
        
        profile = ai_client.load_profile(profile_id)
        if not profile:
            available = [p['id'] for p in ai_client.get_available_profiles()]
            return jsonify({
                'success': False,
                'error': f"Profile '{profile_id}' không tồn tại. Có sẵn: {', '.join(available)}"
            }), 400
        
        ai_client.current_profile = profile_id
        return jsonify({
            'success': True,
            'name': profile.get('name', profile_id),
            'profile': profile_id
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/health', methods=['GET'])
def health():
    return jsonify({
        'status': 'ok',
        'ai_ready': ai_client.client is not None,
        'current_profile': ai_client.current_profile
    })

# ==================== FILE UPLOAD ====================
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/api/upload', methods=['POST'])
def upload_file():
    try:
        if 'files' not in request.files:
            return jsonify({'error': 'No files provided'}), 400
        
        files = request.files.getlist('files')
        uploaded = []
        
        for file in files:
            if file and file.filename and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                # Add timestamp to avoid conflicts
                import time
                timestamp = int(time.time() * 1000)
                unique_name = f"{timestamp}_{filename}"
                filepath = UPLOADS_DIR / unique_name
                file.save(str(filepath))
                uploaded.append({
                    'filename': unique_name,
                    'original': file.filename,
                    'url': f'/uploads/{unique_name}'
                })
        
        return jsonify({'success': True, 'files': uploaded})
        
    except Exception as e:
        print(f"Upload error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/uploads/<filename>')
def serve_upload(filename):
    return send_from_directory(str(UPLOADS_DIR), filename)

# ==================== MAIN ====================
if __name__ == '__main__':
    print("[*] Starting Bong X AI Web Server...")
    print(f"[>] Profiles: {PROFILES_DIR}")
    print(f"[>] Uploads: {UPLOADS_DIR}")
    print(f"[>] AI Ready: {ai_client.client is not None}")
    print(f"[>] Current Profile: {ai_client.current_profile}")
    print("\n[*] Open http://localhost:5000 in your browser\n")
    
    app.run(host='0.0.0.0', port=5000, debug=True)
