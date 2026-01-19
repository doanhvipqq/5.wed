import re
import json
import os
from pathlib import Path
from cerebras.cloud.sdk import Cerebras
from telegram import Update
from telegram.ext import ContextTypes
from utils.logger import log
from utils.storage import db

PROFILES_DIR = Path("data/profiles")

class ChatbotHandler:
    def __init__(self):
        self.keys = self.load_keys()
        self.current_key_index = 0
        self.client = None
        self.model_name = "qwen-3-32b"
        self.abbreviations = self.load_abbreviations()
        self.current_profile = "default"
        self.setup_ai()

    def load_keys(self):
        keys = []
        try:
            with open("api_keys.json", "r") as f:
                data = json.load(f)
                keys = data.get("cerebras_api_keys", [])
        except FileNotFoundError:
            log.error("api_keys.json not found!")
        
        if not keys:
            log.warning("No keys found in api_keys.json!")
        return keys

    def rotate_key(self):
        if not self.keys:
            return False
        self.current_key_index = (self.current_key_index + 1) % len(self.keys)
        self.setup_ai()
        log.info(f"Switched to API Key index: {self.current_key_index}")
        return True

    def load_abbreviations(self):
        return db.load("viettat", default={})

    def normalize_input(self, text):
        if not text:
            return ""
        for abbr, full in self.abbreviations.items():
            pattern = re.compile(r'\b' + re.escape(abbr) + r'\b', re.IGNORECASE)
            text = pattern.sub(full, text)
        return text

    def setup_ai(self):
        if not self.keys:
            log.warning("No API Keys available! AI Module is offline.")
            return
        current_key = self.keys[self.current_key_index]
        try:
            self.client = Cerebras(api_key=current_key)
        except Exception as e:
            log.error(f"Failed to initialize Cerebras SDK: {e}")

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

    def load_profile(self, profile_name: str):
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
        cleaned = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL).strip()
        cleaned = re.sub(r'(?<!\*)\*(?!\*)', '**', cleaned) # Start to Bold
        if not cleaned:
            return "..."
        return cleaned

    async def generate_reply(self, user_input, history=""):
        full_prompt = f"Chat History:\n{history}\n\nUser: {user_input}"
        max_retries = len(self.keys) if self.keys else 1
        attempts = 0

        while attempts < max_retries:
            try:
                if not self.client:
                    self.setup_ai()
                    if not self.client:
                        raise Exception("No client available")

                # Cerebras mostly sync, run in executor
                # (Simple wrapper since cerebras sdk might block)
                import asyncio
                loop = asyncio.get_running_loop()
                
                response = await loop.run_in_executor(
                    None,
                    lambda: self.client.chat.completions.create(
                        model=self.model_name,
                        messages=[
                            {"role": "system", "content": self.get_system_prompt()},
                            {"role": "user", "content": full_prompt}
                        ],
                        temperature=0.9, 
                        max_tokens=800 # Telegram allows longer messages
                    )
                )
                return response
            except Exception as e:
                error_msg = str(e)
                if "401" in error_msg or "429" in error_msg:
                    log.warning(f"Key failed ({error_msg}). Rotating...")
                    if self.rotate_key():
                        attempts += 1
                        continue
                raise e
        
        raise Exception("All API Keys exhausted.")

    async def list_profiles(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        profiles = self.get_available_profiles()
        if not profiles:
            await update.message.reply_text("❌ Không tìm thấy profile nào!")
            return
        
        text = f"📋 **Danh sách Profile**\nProfile hiện tại: `{self.current_profile}`\n\n"
        for p in profiles:
            status = "✅" if p["id"] == self.current_profile else "⚪"
            text += f"{status} **{p['name']}** (`{p['id']}`)\n_{p['description']}_\n\n"
        
        text += "Dùng `/profile <tên>` để đổi"
        await update.message.reply_text(text, parse_mode="Markdown")

    async def set_profile(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        ADMIN_ID = 7509896689
        user_id = update.effective_user.id
        
        args = context.args
        if not args:
            # Show current
            profile = self.load_profile(self.current_profile)
            if profile:
                text = (
                    f"👤 **Profile: {profile.get('name', self.current_profile)}**\n"
                    f"ID: `{self.current_profile}`\n"
                    f"Tính cách: {profile.get('personality', 'N/A')}\n"
                    f"Mô tả: {profile.get('description', 'N/A')}\n\n"
                    f"Dùng `/profiles` để xem tất cả"
                )
                await update.message.reply_text(text, parse_mode="Markdown")
                return

            await update.message.reply_text(f"❌ Profile hiện tại: `{self.current_profile}`")
            return

        # Admin check for changing profile
        if user_id != ADMIN_ID:
            await update.message.reply_text("❌ Chỉ admin mới được đổi profile!")
            return

        profile_name = args[0].lower()
        profile = self.load_profile(profile_name)
        if not profile:
            available = [p["id"] for p in self.get_available_profiles()]
            await update.message.reply_text(f"❌ Profile `{profile_name}` không tồn tại!\nCó sẵn: {', '.join(available)}")
            return
        
        self.current_profile = profile_name
        text = (
            f"✅ **Đã đổi Profile!**\n"
            f"Đã chuyển sang: **{profile.get('name', profile_name)}**\n"
            f"Tính cách: {profile.get('personality', 'N/A')}"
        )
        await update.message.reply_text(text, parse_mode="Markdown")

    async def chat_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self.client:
            await update.message.reply_text("Bot chưa sẵn sàng 😢")
            return
        
        user_input = " ".join(context.args)
        if not user_input:
            await update.message.reply_text("Hãy nhập nội dung chat! Ví dụ: `/chat Xin chào`")
            return

        await self._process_chat(update, user_input)

    async def on_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self.client:
            return # Silent fail if not ready or not intended
            
        user_input = update.message.text
        # Respond to all messages in groups and private chats
        # Bot will reply to every text message like a direct conversation
        
        await self._process_chat(update, user_input)

    async def _process_chat(self, update: Update, raw_content: str):
        normalized_content = self.normalize_input(raw_content)
        user_id = str(update.effective_user.id)
        
        # Logging
        current_logs = db.load("logs", default={})
        if user_id not in current_logs:
            current_logs[user_id] = []
        
        current_logs[user_id].append(f"User: {normalized_content}")
        if len(current_logs[user_id]) > 20:
            current_logs[user_id] = current_logs[user_id][-20:]
        db.save("logs", current_logs)
        
        await update.message.chat.send_action(action="typing")
        
        try:
            history = "\n".join(current_logs.get(user_id, [])[:-1])
            response = await self.generate_reply(normalized_content, history)
            
            raw_text = response.choices[0].message.content.strip()
            reply_text = self.clean_response(raw_text)
            
            current_logs[user_id].append(f"Bot: {reply_text}")
            db.save("logs", current_logs)
            
            log.info(f"Chat [{self.current_profile}] - User: {normalized_content}")
            log.info(f"Chat [{self.current_profile}] - Bot: {reply_text[:50]}...")
            
            await update.message.reply_text(reply_text)
            
        except Exception as e:
            log.error(f"AI Error: {e}")
            await update.message.reply_text(f"Bot bị lỗi: {str(e)[:50]}")
