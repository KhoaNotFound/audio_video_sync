# 🎙 Audio-Video Sync Tool

Ứng dụng web tự động đồng bộ file âm thanh thu ngoài (micro cài áo, phòng thu) với video bằng thuật toán xử lý tín hiệu số (**Spectral Flux + Onset Peak-Voting + Cross-Correlation**).

---

## ✨ Tính năng nổi bật

- **Đồng bộ tự động & chính xác**: Tìm độ lệch thời gian (time offset) giữa âm thanh video và âm thanh rời với độ chính xác mili-giây.
- **Tự động chèn Silence**: Khi file audio ngắn hơn video, hệ thống tự động bù khoảng lặng ở cuối để đảm bảo audio xuất ra khớp trọn vẹn với toàn bộ video.
- **Cơ chế kiểm soát chất lượng (Quality Gate)**:
  - Nếu âm thanh quá nhiều tạp âm hoặc không tìm được điểm khớp đáng tin cậy: Từ chối xử lý và thông báo người dùng thu âm lại.
  - Nếu độ khớp ở mức ranh giới: Xuất file kèm cảnh báo màu vàng để người dùng nghe kiểm tra lại.
- **Hỗ trợ đa định dạng**:
  - **Video input**: MP4, MOV, MKV, MXF, AVI, WebM, TS,...
  - **Audio input**: M4A, MP3, WAV, FLAC, AAC, OGG, Opus,...
  - **Audio output**: Tùy chọn xuất ra M4A (AAC 256k), MP3 (320k), WAV (PCM), FLAC (lossless), Opus (128k), AAC raw (mặc định tự nhận diện theo đuôi file upload).
- **Tự động tải về**: Sau khi xử lý xong, trình duyệt sẽ tự động kích hoạt tải file audio đã căn chỉnh về máy.
- **Giao diện hiện đại**: Thiết kế Dark Mode tối giản, kéo thả 2 vùng độc lập, hiển thị dung lượng file và tiến trình xử lý trực quan.

---

## 📁 Cấu trúc thư mục dự án

```text
audio_video_sync/
├── app.py              # Backend FastAPI (xử lý DSP, API sync, serve download)
├── index.html          # Frontend giao diện người dùng (Vanilla HTML/CSS/JS)
├── requirements.txt    # Danh sách thư viện Python cần thiết
├── render.yaml         # Cấu hình Blueprint tự động cho Render.com
├── vercel.json         # Cấu hình static route cho Vercel
├── run_server.py       # Script tiện ích chạy local dev server
├── README.md           # Hướng dẫn dự án & tài liệu triển khai
└── .gitignore          # Danh sách file/folder loại trừ khi push GitHub
```

---

## 💻 Chạy cục bộ (Local Development)

### 1. Yêu cầu hệ thống
- Python 3.9 trở lên
- Git

### 2. Cài đặt môi trường
```bash
# 1. Tạo môi trường ảo
python -m venv .venv

# 2. Kích hoạt môi trường ảo
# Trên Windows (PowerShell):
.venv\Scripts\Activate.ps1
# Trên Linux / macOS:
source .venv/bin/activate

# 3. Cài đặt các thư viện cần thiết
pip install -r requirements.txt
```

### 3. Khởi chạy Server
```bash
python run_server.py
```
Hoặc dùng trực tiếp lệnh `uvicorn`:
```bash
uvicorn app:app --reload --host 127.0.0.1 --port 8000
```
Sau đó mở trình duyệt và truy cập: **`http://127.0.0.1:8000`**

---

## 🚀 Hướng dẫn Deploy (Render cho Backend + Vercel cho Frontend)

Quy trình chuẩn gồm 3 giai đoạn:
1. **Đẩy mã nguồn lên GitHub** (chỉ lọc các file cần thiết).
2. **Deploy Backend lên Render** (chạy Python/FastAPI và xử lý âm thanh).
3. **Deploy Frontend lên Vercel** (phục vụ giao diện tĩnh và gọi API Render).

---

### BƯỚC 1: Khởi tạo Git & Đẩy code lên GitHub

#### 1. Các file CẦN đẩy lên GitHub:
- `app.py`
- `index.html`
- `requirements.txt`
- `render.yaml`
- `vercel.json`
- `run_server.py`
- `README.md`
- `.gitignore`

> ⚠️ **TUYỆT ĐỐI KHÔNG đẩy lên GitHub**:
> - Thư mục `data/` (chứa video, audio dung lượng hàng trăm MB/GB).
> - Thư mục `.venv/` (môi trường Python ảo cá nhân).
> - Thư mục `__pycache__/`, `.work/`, các file `*.log`, `*.txt` tạm.
> *(File `.gitignore` đi kèm đã cấu hình sẵn để tự động loại trừ các file này)*.

#### 2. Các lệnh đẩy lên GitHub:
```bash
# 1. Khởi tạo git repository trong thư mục dự án
git init

# 2. Thêm các file vào danh sách commit
git add .

# 3. Kiểm tra lại trạng thái (đảm bảo không có data/ hay .venv/)
git status

# 4. Tạo commit đầu tiên
git commit -m "Initial commit: Audio-Video Sync Web App"

# 5. Đổi tên nhánh chính thành main
git branch -M main

# 6. Liên kết với kho lưu trữ GitHub của bạn (thay YOUR_USERNAME và YOUR_REPO bằng link thật)
git remote add origin https://github.com/YOUR_USERNAME/YOUR_REPO.git

# 7. Đẩy mã nguồn lên GitHub
git push -u origin main
```

---

### BƯỚC 2: Triển khai Backend lên Render.com

Render là nền tảng máy chủ phù hợp để chạy FastAPI và xử lý tính toán tín hiệu âm thanh kèm FFmpeg.

1. Đăng nhập vào [Render.com](https://dashboard.render.com/).
2. Nhấn nút **New +** và chọn **Web Service**.
3. Chọn **Build and deploy from a Git repository** và kết nối với repository GitHub vừa tạo ở Bước 1.
4. Cấu hình các thông số dịch vụ:
   - **Name**: `audio-sync-backend` (hoặc tên tùy thích)
   - **Region**: Singapore (hoặc Oregon / Frankfurt - ưu tiên gần bạn nhất)
   - **Branch**: `main`
   - **Root Directory**: Để trống (mặc định thư mục gốc)
   - **Runtime**: `Python 3`
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `uvicorn app:app --host 0.0.0.0 --port $PORT`
   - **Instance Type**: `Free` (512 MB RAM, 0.1 CPU)
5. Nhấn **Create Web Service**.
6. Render sẽ tự động kéo code về, cài đặt gói phụ thuộc và khởi chạy. Khi hoàn tất, Render sẽ cung cấp URL dịch vụ, ví dụ:
   ```text
   https://audio-sync-backend.onrender.com
   ```
   *(Hãy copy lại link này để dùng cho Bước 3)*.

> 💡 **Lưu ý về Render Free Tier**:
> - Dịch vụ miễn phí trên Render sẽ tạm dừng (spin-down) sau 15 phút không có lượt truy cập.
> - Lần truy cập đầu tiên sau khi ngủ sẽ mất khoảng 40–50 giây để khởi động lại (Cold Start). Sau khi thức giấc, hệ thống phản hồi bình thường.

---

### BƯỚC 3: Triển khai Frontend lên Vercel

Vercel phục vụ giao diện tĩnh (`index.html`) cực nhanh qua mạng CDN toàn cầu.

1. Đăng nhập vào [Vercel](https://vercel.com/).
2. Nhấn **Add New...** ➔ **Project**.
3. Chọn kho lưu trữ GitHub chứa dự án của bạn và nhấn **Import**.
4. Cấu hình Project:
   - **Framework Preset**: Chọn **Other**
   - **Root Directory**: `./` (mặc định)
   - **Build and Output Settings**: Giữ nguyên mặc định (không cần lệnh build vì đây là file HTML tĩnh)
5. Nhấn **Deploy**.
6. Sau vài giây, Vercel sẽ cung cấp link trang web của bạn, ví dụ:
   ```text
   https://audio-sync-frontend.vercel.app
   ```

---

### BƯỚC 4: Kết nối Frontend Vercel với Backend Render

Khi mở trang web trên Vercel, bạn có 2 cách cực kỳ đơn giản để kết nối:

#### Cách 1 (Nhanh nhất - Không cần sửa code):
1. Mở trang web Vercel trên trình duyệt.
2. Nhìn xuống chân trang (Footer), click vào dòng chữ: **`⚙️ Đổi Backend Render URL`**.
3. Dán link Render của bạn vào (ví dụ: `https://audio-sync-backend.onrender.com`) và nhấn **OK**.
4. Địa chỉ này sẽ được lưu an toàn trong trình duyệt của bạn (`localStorage`) và sử dụng cho mọi lần sync tiếp theo.

#### Cách 2 (Cố định vĩnh viễn trong code):
Trước khi push git, mở file `index.html`, tìm dòng:
```javascript
const RENDER_BACKEND_URL = '';
```
và điền URL Render của bạn:
```javascript
const RENDER_BACKEND_URL = 'https://audio-sync-backend.onrender.com';
```
Sau đó commit và push lên GitHub, Vercel sẽ tự động cập nhật ngay lập tức.

---

## ⚙️ Các thông số kỹ thuật thuật toán

| Tham số | Giá trị mặc định | Giải thích |
| :--- | :--- | :--- |
| **Sample Rate (SR)** | `16,000 Hz` | Tần số lấy mẫu chuẩn để phân tích giọng nói |
| **Hop Size / Frame Size** | `10 ms / 40 ms` | Độ phân giải thời gian và cửa sổ FFT |
| **Dải tần phân tích** | `200 – 4,000 Hz` | Dải tần số mang nhiều năng lượng nhất của tiếng nói người |
| **Wide-band Retry** | `150 – 8,000 Hz` | Tự động kích hoạt quét dải rộng khi tín hiệu yếu |
| **Ngưỡng loại bỏ nhiễu** | `Votes < 5` hoặc `Corr < 0.08` | Chất lượng không đạt ➔ Yêu cầu thu âm lại |
| **Ngưỡng cảnh báo** | `Votes < 15` hoặc `Corr < 0.30` | Cho phép xuất file nhưng gắn cảnh báo tin cậy thấp |

---

## 🛡 Bản quyền & Giấy phép
Dự án được xây dựng cho mục đích tự động hóa quy trình dựng video và hậu kỳ âm thanh.
Mã nguồn mở theo giấy phép MIT.
