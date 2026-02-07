# Golike Instagram Bot

Bot Telegram tự động làm job Like/Follow trên Golike.

## Tính năng

- ✅ Hỗ trợ nhiều tài khoản Instagram
- ✅ Tự động chuyển tài khoản khi đạt giới hạn job
- ✅ Hỗ trợ đăng nhập bằng Cookies hoặc User/Pass
- ✅ Hỗ trợ xác thực 2FA
- ✅ Hỗ trợ Proxy cho từng tài khoản
- ✅ Thông báo chi tiết qua Telegram

## Cấu trúc thư mục

```
├── bot.py              # File chính
├── config.json         # Cấu hình Telegram Token
├── data/               # Dữ liệu (cookies, config...)
└── loi/                # Module lõi
    ├── cauhinh.py      # Cấu hình chung
    ├── dangnhap.py     # Đăng nhập Instagram
    ├── golike.py       # API Golike
    ├── instagram.py    # Xử lý Instagram
    ├── thongbao.py     # Gửi thông báo Telegram
    ├── tienich.py      # Tiện ích
    └── xulyjob.py      # Xử lý Job
```

## Cài đặt

```bash
pip install python-telegram-bot requests cloudscraper
```

## Sử dụng

1. Chạy bot:
```bash
python bot.py
```

2. Nhập Telegram Bot Token khi được hỏi

3. Mở Telegram và chat `/start` với bot

## Lệnh Bot

- `/start` - Bắt đầu cấu hình và chạy Tool
- `/stop` - Dừng Tool
- `/help` - Xem hướng dẫn
- `/cancel` - Hủy cấu hình

## Tác giả

- GitHub: [doanhvipqq](https://github.com/doanhvipqq)
