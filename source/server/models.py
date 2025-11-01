from werkzeug.security import generate_password_hash, check_password_hash
from source.server.extensions import db
from datetime import datetime

# Model cho bảng User
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(128))

    # Relationship với Room
    rooms_owned = db.relationship('Room', backref='host', lazy=True)
    
    def set_password(self, password):
        """Tạo hash cho mật khẩu"""
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        """Kiểm tra hash mật khẩu"""
        return check_password_hash(self.password_hash, password)

    def __repr__(self):
        return f'<User {self.username}>'

# Model cho bảng Room
class Room(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    room_id = db.Column(db.String(80), unique=True, nullable=False)
    host_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    game_started = db.Column(db.Boolean, default=False)
    current_round = db.Column(db.Integer, default=0)
    max_rounds = db.Column(db.Integer, default=10)
    
    # Relationship với Player
    players = db.relationship('Player', backref='room', lazy=True, cascade='all, delete-orphan')

    def __repr__(self):
        return f'<Room {self.room_id}>'

# Model cho bảng Player (người chơi trong phòng)
class Player(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    room_id = db.Column(db.Integer, db.ForeignKey('room.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    score = db.Column(db.Integer, default=0)
    joined_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    socket_id = db.Column(db.String(120), nullable=True)  # Socket.IO session ID

    # Relationship với User
    user = db.relationship('User', backref=db.backref('player_sessions', lazy=True))

    def __repr__(self):
        return f'<Player {self.user_id} in Room {self.room_id}>'