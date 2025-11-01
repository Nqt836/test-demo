from source.server.extensions import db
from source.server.models import User

def validate_username(username):
    """Kiểm tra username hợp lệ: 3-20 ký tự, chỉ chữ số, chữ cái, underscore"""
    if not username or len(username) < 3 or len(username) > 20:
        return False, "Tên đăng nhập phải 3-20 ký tự."
    if not all(c.isalnum() or c == '_' for c in username):
        return False, "Tên đăng nhập chỉ gồm chữ cái, số, và _"
    return True, ""

def validate_password(password):
    """Kiểm tra password hợp lệ: tối thiểu 6 ký tự"""
    if not password or len(password) < 6:
        return False, "Mật khẩu phải tối thiểu 6 ký tự."
    return True, ""

def register_user(username, password): 
    """
    Đăng ký người dùng mới.
    Trả về (True, "Success") nếu thành công.
    Trả về (False, "Error Message") nếu thất bại.
    """
    # Validate
    is_valid, msg = validate_username(username)
    if not is_valid:
        return (False, msg)
    
    is_valid, msg = validate_password(password)
    if not is_valid:
        return (False, msg)
    
    try:
        # Check if user exists
        existing_user = User.query.filter_by(username=username).first()
        if existing_user: 
            return (False, "Tên đăng nhập đã tồn tại.") 
        
        # Create new user
        new_user = User(username=username)
        new_user.set_password(password) 

        db.session.add(new_user)
        db.session.commit() 
        return (True, "Đăng ký thành công!")
    except Exception as e:
        try:
            db.session.rollback()
        except:
            pass
        print(f"[Auth] Register error: {type(e).__name__}: {str(e)}")
        return (False, f"Lỗi máy chủ: {str(e)}")
        
def login_user(username, password):
    """
    Kiểm tra đăng nhập.
    Trả về đối tượng User nếu hợp lệ.
    Trả về None nếu không hợp lệ.
    """
    if not username or not password:
        return None
    
    try:
        user = User.query.filter_by(username=username).first()
        if user and user.check_password(password):
            return user
    except Exception as e:
        print(f"[Auth] Login error: {type(e).__name__}: {str(e)}")
    
    return None
