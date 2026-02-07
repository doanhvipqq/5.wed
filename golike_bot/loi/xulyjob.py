# ==========================================
# XỬ LÝ JOB - Logic chính xử lý Like/Follow
# ==========================================

import time
import itertools
import random
import os
import json
import logging
from .golike import GolikeAPI
from .instagram import InstagramClient
from .thongbao import TelegramNotifier
from .tienich import safe_dict_check, get_account_proxy, format_proxy_for_requests
from .cauhinh import LOCK_TIME_SECONDS

# Cấu hình logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("XuLyJob")

def create_job_cycler(ratio_str, lam):
    """
    Tạo vòng lặp job theo tỷ lệ
    ratio_str: "1,1" -> 1 like, 1 follow
    lam: ["like", "follow"] or ["like"] or ["follow"]
    """
    if not lam:
        return itertools.cycle(["like"])  # Mặc định
    
    if len(lam) == 1:
        return itertools.cycle(lam)
        
    try:
        ratios = [int(x) for x in ratio_str.split(',')]
        if len(ratios) != 2:
            ratios = [1, 1]
    except:
        ratios = [1, 1]
        
    pattern = []
    if "like" in lam:
        pattern.extend(["like"] * ratios[0])
    if "follow" in lam:
        pattern.extend(["follow"] * ratios[1])
        
    if not pattern:
        pattern = lam
        
    return itertools.cycle(pattern)

class Worker:
    def __init__(self, config, accounts, auth, token, chat_id):
        self.config = config
        self.accounts = accounts  # Danh sách dict
        self.auth = auth
        self.notifier = TelegramNotifier(token, chat_id)
        self.golike = GolikeAPI(auth)
        self.instagram = InstagramClient()
        
        self.delay = config.get('delay', 5)
        self.job_limit = config.get('job_limit', 10)
        self.fail_limit = config.get('doiacc', 5)
        self.lam = config.get('lam', ['like', 'follow'])
        self.ratio_str = config.get('job_ratio_str', "1,1")
        self.lannhan = config.get('lannhan', 'y')
        self.ai_autobot = config.get('ai_autobot', False)
        self.scroll_duration = config.get('scroll_duration', 10)
        
        self.total_money = 0
        self.job_done_count = 0
        
        # Index tài khoản hiện tại (KHÔNG dùng itertools.cycle để stay on one account)
        self.current_account_index = 0
        self.job_cycler = create_job_cycler(self.ratio_str, self.lam)
        
        # Khởi tạo counters cho tất cả accounts
        for acc in self.accounts:
            acc['success_count'] = 0
            acc['fail_count'] = 0
            acc['is_locked'] = False
            acc['lock_until'] = 0
        
    def get_current_account(self):
        """Lấy tài khoản hiện tại"""
        if not self.accounts:
            return None
        return self.accounts[self.current_account_index]
    
    def switch_to_next_account(self, reason=""):
        """Chuyển sang tài khoản tiếp theo CHỈ KHI đạt giới hạn hoặc lỗi"""
        old_username = self.accounts[self.current_account_index]['username']
        old_count = self.accounts[self.current_account_index].get('success_count', 0)
        
        # Reset counter của acc vừa dùng
        self.accounts[self.current_account_index]['success_count'] = 0
        
        # Chuyển sang account tiếp theo
        self.current_account_index = (self.current_account_index + 1) % len(self.accounts)
        new_username = self.accounts[self.current_account_index]['username']
        
        # Thông báo chi tiết
        self.notifier.send_message(
            f"🔄 <b>CHUYỂN TÀI KHOẢN</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"📤 Từ: <code>{old_username}</code>\n"
            f"   └─ Đã hoàn thành: {old_count}/{self.job_limit} job\n"
            f"   └─ Lý do: {reason}\n"
            f"📥 Đến: <code>{new_username}</code>\n"
            f"   └─ Mục tiêu: {self.job_limit} job\n"
            f"━━━━━━━━━━━━━━━━━━━━"
        )
        logger.info(f"Chuyển từ {old_username} -> {new_username}. Lý do: {reason}")
        
    def save_cookies(self, username, cookies):
        """Lưu cookies cho tài khoản"""
        os.makedirs("data/cookies", exist_ok=True)
        path = f"data/cookies/{username}.txt"
        try:
            with open(path, 'w', encoding='utf-8') as f:
                f.write(cookies)
        except Exception as e:
            logger.error(f"Lỗi lưu cookies cho {username}: {e}")

    def run(self):
        """Vòng lặp chính xử lý job - GIỮ NGUYÊN 1 ACC đến khi đạt job_limit"""
        self.notifier.send_message(
            f"🚀 <b>BẮT ĐẦU CHẠY TOOL</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"👤 Số tài khoản: {len(self.accounts)}\n"
            f"🎯 Giới hạn job/acc: {self.job_limit}\n"
            f"⏱️ Delay: {self.delay}s\n"
            f"📝 Loại job: {', '.join(self.lam)}\n"
            f"━━━━━━━━━━━━━━━━━━━━"
        )
        logger.info(f"Worker khởi động với {len(self.accounts)} tài khoản.")
        
        # Thông báo bắt đầu với account đầu tiên
        first_acc = self.get_current_account()
        if first_acc:
            self.notifier.send_message(f"▶️ Bắt đầu với tài khoản: <code>{first_acc['username']}</code>")
        
        while True:
            current_acc = self.get_current_account()
            if not current_acc:
                self.notifier.send_message("❌ <b>Không có tài khoản nào để chạy!</b>")
                break
                
            username = current_acc['username']
            account_id = current_acc['id']
            
            # 1. Kiểm tra khóa
            if current_acc.get('is_locked'):
                if time.time() < current_acc.get('lock_until', 0):
                    remaining = int(current_acc['lock_until'] - time.time())
                    logger.info(f"Tài khoản {username} đang bị khóa. Còn {remaining}s")
                    # Chuyển sang account khác trong khi chờ
                    self.switch_to_next_account(f"Bị khóa, còn {remaining}s")
                    time.sleep(1)
                    continue
                else:
                    current_acc['is_locked'] = False
                    current_acc['lock_until'] = 0
                    self.notifier.send_message(f"🔓 <b>{username}</b> đã được mở khóa!")
                    logger.info(f"Tài khoản {username} đã mở khóa.")
            
            # 2. Kiểm tra giới hạn thất bại liên tiếp
            if current_acc.get('fail_count', 0) >= self.fail_limit:
                self.switch_to_next_account(f"Thất bại liên tiếp {self.fail_limit} lần")
                current_acc['fail_count'] = 0
                time.sleep(1)
                continue
                
            # 3. Kiểm tra ĐÃ ĐẠT giới hạn thành công -> CHUYỂN ACC
            if current_acc.get('success_count', 0) >= self.job_limit:
                self.switch_to_next_account(f"✅ Hoàn thành {self.job_limit} job")
                time.sleep(1)
                continue
                
            # Lấy loại job tiếp theo
            desired_job_type = next(self.job_cycler)
            current_success = current_acc.get('success_count', 0)
            
            # 4. Lấy Job từ Golike
            logger.info(f"[{username}] Đang lấy job ({desired_job_type})... [{current_success}/{self.job_limit}]")
            nhanjob = self.golike.get_job(account_id)
            
            if nhanjob.get('status') != 200:
                msg = nhanjob.get('message', 'Lỗi không xác định')
                if nhanjob.get('status') == 400:
                    logger.warning(f"[{username}] Lấy job thất bại: {msg}")
                    self.notifier.send_message(f"⚠️ <b>{username}</b>: Không lấy được job - {msg}")
                else:
                    logger.warning(f"[{username}] Không có job. Status: {nhanjob.get('status')}")
                time.sleep(2)
                continue
                
            job_data = nhanjob.get('data')
            if not job_data:
                time.sleep(1)
                continue
                
            ads_id = job_data.get('id')
            object_id = job_data.get('object_id')
            link = job_data.get('link')
            job_type = job_data.get('type')  # 'like' or 'follow'
            
            # Kiểm tra loại job
            if job_type not in self.lam:
                self.golike.report_job(ads_id, object_id, account_id, job_type)
                continue
                
            # 5. Thực hiện Job trên Instagram
            logger.info(f"[{username}] Đang thực hiện {job_type} trên {object_id}")
            self.notifier.send_message(
                f"🚀 <b>ĐANG LÀM JOB</b>\n"
                f"👤 {username} [{current_success + 1}/{self.job_limit}]\n"
                f"📝 {job_type.upper()}: {object_id}"
            )
            
            success = False
            new_cookies = current_acc['cookies']
            result_info = {}
            
            # Lấy proxy cho tài khoản này
            proxy_dict = get_account_proxy(username)
            
            if job_type == 'follow':
                success, new_cookies, result_info = self.instagram.handle_follow_job(current_acc, object_id, proxy_dict)
            elif job_type == 'like':
                media_id = object_id
                success, new_cookies, result_info = self.instagram.handle_like_job(current_acc, media_id, link, proxy_dict)
            
            # Cập nhật Cookies
            if new_cookies != current_acc['cookies']:
                current_acc['cookies'] = new_cookies
                self.save_cookies(username, new_cookies)
                
            # Xử lý kết quả
            if not success:
                if result_info.get('locked'):
                    current_acc['is_locked'] = True
                    current_acc['lock_until'] = time.time() + LOCK_TIME_SECONDS
                    lock_minutes = LOCK_TIME_SECONDS // 60
                    self.notifier.send_message(
                        f"🚨 <b>TÀI KHOẢN BỊ KHÓA</b>\n"
                        f"━━━━━━━━━━━━━━━━━━━━\n"
                        f"👤 {username}\n"
                        f"❌ Lỗi: {result_info.get('message')}\n"
                        f"⏱️ Tạm khóa: {lock_minutes} phút\n"
                        f"━━━━━━━━━━━━━━━━━━━━"
                    )
                    # Chuyển acc ngay khi bị khóa
                    self.switch_to_next_account("Tài khoản bị khóa")
                else:
                    current_acc['fail_count'] = current_acc.get('fail_count', 0) + 1
                    fail_count = current_acc['fail_count']
                    self.golike.report_job(ads_id, object_id, account_id, job_type)
                    self.notifier.send_message(
                        f"❌ <b>JOB THẤT BẠI</b> [{fail_count}/{self.fail_limit}]\n"
                        f"👤 {username}\n"
                        f"📝 {result_info.get('message')}"
                    )
                time.sleep(1)
                continue
                
            # Logic thành công
            if self.ai_autobot:
                time.sleep(self.scroll_duration)
                
            # Delay trước khi hoàn thành
            time.sleep(self.delay)
            
            # 6. Hoàn thành Job
            ok = False
            for i in range(2):
                if i == 1 and self.lannhan == 'n': break
                
                res = self.golike.complete_job(ads_id, account_id)
                if res.get('status') == 200 and res.get('data'):
                    data = res['data']
                    tien = data.get('prices', 0)
                    self.total_money += tien
                    self.job_done_count += 1
                    current_acc['success_count'] = current_acc.get('success_count', 0) + 1
                    current_acc['fail_count'] = 0
                    
                    new_success_count = current_acc['success_count']
                    
                    self.notifier.send_message(
                        f"✅ <b>THÀNH CÔNG</b> [{new_success_count}/{self.job_limit}]\n"
                        f"━━━━━━━━━━━━━━━━━━━━\n"
                        f"👤 {username}\n"
                        f"📝 Loại: {job_type}\n"
                        f"💰 Tiền: +{tien}\n"
                        f"💵 Tổng: {self.total_money}\n"
                        f"━━━━━━━━━━━━━━━━━━━━"
                    )
                    logger.info(f"[{username}] Job hoàn thành. +{tien} [{new_success_count}/{self.job_limit}]")
                    ok = True
                    break
                else:
                    time.sleep(2)
            
            if not ok:
                 self.golike.report_job(ads_id, object_id, account_id, job_type)
                 current_acc['fail_count'] = current_acc.get('fail_count', 0) + 1
                 self.notifier.send_message(f"❌ <b>Hoàn thành thất bại ({username})</b>")
            
            time.sleep(1)

def run_worker(config, accounts, auth, token, chat_id):
    """Hàm chạy worker (được gọi từ multiprocessing)"""
    worker = Worker(config, accounts, auth, token, chat_id)
    try:
        worker.run()
    except KeyboardInterrupt:
        pass
    except Exception as e:
        logger.error(f"Worker gặp sự cố: {e}")
        TelegramNotifier(token, chat_id).send_message(f"🔥 <b>Worker GẶP SỰ CỐ:</b> {e}")
