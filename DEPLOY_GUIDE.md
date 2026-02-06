# Hướng Dẫn Đưa Bóng X AI Lên Web Công Khai

Bạn có 2 cách để đưa web lên mạng:
1. **Render (Khuyên dùng)**: Miễn phí, chạy 24/7, có đường dẫn riêng (vd: `bongx-ai.onrender.com`).
2. **Ngrok**: Nhanh, chạy tạm thời từ máy tính của bạn (tắt máy là mất).

---

## Cách 1: Deploy lên Render (Miễn phí vĩnh viễn)

Mình đã cấu hình sẵn các file `render.yaml` và `requirements.txt`. Bạn chỉ cần làm theo các bước:

### Bước 1: Đẩy code lên GitHub
1. Tạo tài khoản [GitHub](https://github.com) nếu chưa có.
2. Tạo một Repository mới (đặt tên là `bongx-ai`).
3. Mở terminal tại thư mục code (`c:\Users\Administrator\Downloads\aiiibongxx`) và chạy:
   ```bash
   git init
   git add .
   git commit -m "Deploy Bong X AI"
   git branch -M main
   git remote add origin <LINK_REPOSITORY_CUA_BAN>
   git push -u origin main
   ```
   *(Thay `<LINK_REPOSITORY_CUA_BAN>` bằng link repo bạn vừa tạo, ví dụ: `https://github.com/doanhvip12/bongx-ai.git`)*

### Bước 2: Deploy trên Render
1. Đăng ký tài khoản [Render.com](https://render.com) (dùng GitHub đăng nhập).
2. Chọn **New +** -> **Web Service**.
3. Chọn **Build and deploy from a Git repository**.
4. Kết nối với GitHub và chọn repo `bongx-ai` bạn vừa upload.
5. Render sẽ tự động phát hiện file `render.yaml` mình đã tạo.
6. Kéo xuống phần **Environment Variables**, thêm:
   - Key: `CER_API_KEY`
   - Value: `<API_KEY_CUA_BAN>` (lấy trong file `api_keys.json`)
7. Bấm **Create Web Service**.

Đợi khoảng 2-3 phút, Render sẽ cấp cho bạn một đường dẫn (ví dụ: `https://bongx-ai-web.onrender.com`). Web đã online! 🎉

---

## Cách 2: Dùng Ngrok (Nhanh, để test ngay)

Dùng cách này nếu bạn muốn gửi link cho bạn bè xem ngay lập tức mà không cần GitHub.

1. Tải [Ngrok](https://ngrok.com/download) và cài đặt.
2. Đăng ký tài khoản Ngrok để lấy Authtoken.
3. Mở terminal, chạy lệnh sau để kết nối tài khoản:
   ```bash
   ngrok config add-authtoken <TOKEN_CUA_BAN>
   ```
4. Đảm bảo server Bóng X đang chạy (`python app.py`).
5. Mở một terminal khác, chạy:
   ```bash
   ngrok http 5000
   ```
6. Copy dòng **Forwarding** (ví dụ: `https://a1b2-c3d4.ngrok-free.app`) gửi cho bạn bè.

> **Lưu ý**: Link Ngrok sẽ chết khi bạn tắt cửa sổ terminal hoặc tắt máy tính.
