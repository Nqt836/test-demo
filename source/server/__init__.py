import os
from flask import Flask

# Import các extensions
from source.server.extensions import db, socketio

def create_app():
    """Application Factory"""
    
    # --- Cấu hình đường dẫn ---
    base_dir = os.path.abspath(os.path.dirname(__file__))
    
    # --- Trỏ templates tới source/client/templates ---
    template_dir = os.path.join(base_dir, '..', 'client', 'templates')
    # --- Tạo folder static ảo từ client/css và server/js ---
    # CSS nằm trong client/css, JS nằm trong server/js
    static_dir = os.path.join(base_dir, '..', 'client')

    # Khởi tạo Flask với template và static folder
    app = Flask(__name__, template_folder=template_dir, static_folder=static_dir, static_url_path='/static')
    
    # --- Thêm thư mục JS từ server/js vào static ---
    # Để Flask phục vụ JS từ /static/js/...
    from flask import send_from_directory
    
    @app.route('/static/js/<path:filename>')
    def serve_server_js(filename):
        """Phục vụ JS từ server/js"""
        js_dir = os.path.join(base_dir, 'js')
        return send_from_directory(js_dir, filename)
    
    # --- Phục vụ media files từ statics folder ---
    @app.route('/statics/<path:filepath>')
    def serve_statics(filepath):
        """Phục vụ ảnh, video từ statics folder"""
        statics_dir = os.path.join(base_dir, '..', '..', 'statics')
        return send_from_directory(statics_dir, filepath)

    # --- Cấu hình App ---
    app.config['SECRET_KEY'] = 'your-very-secret-key-12345'
    db_path = os.path.join(base_dir, '..', '..', 'users.db')
    app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{db_path}'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    # --- Gán App vào Extensions ---
    db.init_app(app)
    socketio.init_app(app)

    # --- Đăng ký Blueprint (của Nam) ---
    from .routes import http_bp
    app.register_blueprint(http_bp)

  
    # Việc import này sẽ đăng ký các hàm @socketio.on
    from . import events 

    # --- Tạo CSDL ---
    with app.app_context():
        # Import models tại đây để đảm bảo db được khởi tạo
        from . import models 
        db.create_all()

    return app
