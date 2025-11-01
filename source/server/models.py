from werkzeug.security import generate_password_hash, check_password_hash
from source.server.extensions import db
from datetime import datetime

# Model cho bảng User
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(128))

    def set_password(self, password):
        """Tạo hash cho mật khẩu"""
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        """Kiểm tra hash mật khẩu"""
        return check_password_hash(self.password_hash, password)

    def __repr__(self):
        return f'<User {self.username}>'

# Model cho bảng GameRoom
class GameRoom(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    room_id = db.Column(db.String(100), unique=True, nullable=False)  # Tên phòng
    host_name = db.Column(db.String(80), nullable=False)  # Tên host
    player_count = db.Column(db.Integer, default=1)  # Số lượng người chơi
    game_started = db.Column(db.Boolean, default=False)  # Game đã bắt đầu?
    created_at = db.Column(db.DateTime, default=datetime.utcnow)  # Thời gian tạo
    last_activity = db.Column(db.DateTime, default=datetime.utcnow)  # Lần cuối cùng có hoạt động
    
    def __repr__(self):
        return f'<GameRoom {self.room_id} - {self.player_count} players>'