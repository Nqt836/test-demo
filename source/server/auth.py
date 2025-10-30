from source.server.models import db, User

def register_user(username, password):
    """
    Đăng ký người dùng mới.
    Trả về (True, "Success") nếu thành công.
    Trả về (False, "Error Message") nếu thất bại.
    """
    if User.query.filter_by(username=username).first():
        return (False, "Tên đăng nhập đã tồn tại.")
    
    new_user = User(username=username)
    new_user.set_password(password)
    
    try:
        db.session.add(new_user)
        db.session.commit()
        return (True, "Đăng ký thành công!")
    except Exception as e:
        db.session.rollback()
        return (False, f"Lỗi máy chủ: {e}")

def login_user(username, password):
    """
    Kiểm tra đăng nhập.
    Trả về đối tượng User nếu hợp lệ.
    Trả về None nếu không hợp lệ.
    """
    user = User.query.filter_by(username=username).first()
    if user and user.check_password(password):
        return user
    return None