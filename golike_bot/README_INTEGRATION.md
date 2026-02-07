# Hướng dẫn chạy Golike Bot Telegram

Bot này đã được tích hợp vào thư mục `golike_bot`.

## Cách chạy

1. Cài đặt thư viện (nếu chưa):
   ```bash
   pip install -r requirements.txt
   ```

2. Chạy Bot:
   ```bash
   cd golike_bot
   python bot.py
   ```

3. Nhập Token Telegram Bot của bạn khi được hỏi.

## Lưu ý trên Render
Để chạy Bot này trên Render cùng với Web, bạn cần tạo thêm một **Background Worker** (có phí) hoặc chạy nó trên máy tính cá nhân/VPS khác. Gói Free của Render chỉ hỗ trợ Web Service (sẽ tắt nếu không có request) và không cho chạy 2 process cùng lúc ổn định.
