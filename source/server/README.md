# Mô-đun server

Thư mục `source/server/` chứa mã phía server (Flask + Flask-SocketIO).

Hướng dẫn ngắn:
- Khởi tạo virtualenv: `python -m venv venv`
- "Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope Process"
- Kích hoạt (Windows PowerShell): `venv\Scripts\Activate.ps1`
- Cài dependencies: `pip install -r requirements.txt`
- Chạy server (dev): `python source/server/app.py` (hoặc `python -m source.server.app` nếu cần)

Lưu ý:
- Không commit `venv/`, `users.db` hoặc các file media lớn nếu không cần.
- File cấu hình và secret nên quản lý bên ngoài repo (ví dụ .env).
