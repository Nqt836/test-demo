from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash

# Khởi tạo đối tượng SQLAlchemy
db = SQLAlchemy()

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