import os
import uvicorn
from app import app

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    print(f"🚀 Audio Sync Tool running at http://127.0.0.1:{port}")
    uvicorn.run(app, host="127.0.0.1", port=port)
