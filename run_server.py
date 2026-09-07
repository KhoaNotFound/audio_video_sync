import os
import sys
import threading
import time
import webbrowser
import uvicorn
from app import app

def open_browser(url: str):
    time.sleep(1.2)
    try:
        webbrowser.open(url)
    except Exception:
        pass

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    url = f"http://127.0.0.1:{port}"
    print("\n" + "=" * 56)
    print(f" 🚀 Audio Sync Tool đang chạy tại: {url}")
    print(f" 🌐 Đang tự động mở trình duyệt web...")
    print(f" ⏹️  Để dừng server: Nhấn Ctrl + C trong cửa sổ này.")
    print("=" * 56 + "\n")

    threading.Thread(target=open_browser, args=(url,), daemon=True).start()
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="info")
