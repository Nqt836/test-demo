from flask_socketio import SocketIO
from flask_sqlalchemy import SQLAlchemy

# Khởi tạo nhưng chưa gán vào app
db = SQLAlchemy()
socketio = SocketIO(async_mode='eventlet')
