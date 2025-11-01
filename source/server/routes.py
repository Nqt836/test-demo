import os
from flask import (
    Blueprint, render_template, request, redirect, url_for, 
    session, jsonify, send_from_directory
)
from werkzeug.utils import secure_filename
import pathlib

# Import các module logic và models
from source.server.models import User
from source.server.auth import register_user, login_user
import source.server.game_logic as game_logic
from source.server.extensions import socketio # Import socketio cho hàm create_room

# Tạo một "Blueprint" cho các route HTTP
http_bp = Blueprint('http_bp', __name__)

# --- Các tuyến đường HTTP (Auth & Lobby) ---
# Tất cả @app.route được đổi thành @http_bp.route

@http_bp.route('/')
def index():
    """Trang đăng nhập/đăng ký"""
    if 'username' in session:
        return redirect(url_for('http_bp.lobby')) # Sửa url_for
    return render_template('index.html')

@http_bp.route('/login', methods=['POST'])
def handle_login():
    """Xử lý form đăng nhập"""
    try:
        data = request.json
        if not data or 'username' not in data or 'password' not in data:
            return jsonify({"success": False, "message": "Thiếu username hoặc password"}), 400
        
        user = login_user(data['username'], data['password'])
        if user:
            session['username'] = user.username
            session['user_id'] = user.id
            return jsonify({"success": True, "message": "Đăng nhập thành công!"})
        return jsonify({"success": False, "message": "Sai tên đăng nhập hoặc mật khẩu."})
    except Exception as e:
        return jsonify({"success": False, "message": f"Lỗi: {str(e)}"}), 500

@http_bp.route('/register', methods=['POST'])
def handle_register():
    """Xử lý form đăng ký"""
    try:
        data = request.json
        if not data or 'username' not in data or 'password' not in data:
            return jsonify({"success": False, "message": "Thiếu username hoặc password"}), 400
        
        success, message = register_user(data['username'], data['password'])
        return jsonify({"success": success, "message": message})
    except Exception as e:
        return jsonify({"success": False, "message": f"Lỗi: {str(e)}"}), 500

@http_bp.route('/logout')
def logout():
    session.pop('username', None)
    session.pop('user_id', None)
    return redirect(url_for('http_bp.index')) # Sửa url_for

@http_bp.route('/lobby')
def lobby():
    """Sảnh chờ"""
    if 'username' not in session:
        return redirect(url_for('http_bp.index')) # Sửa url_for
    return render_template('lobby.html', username=session['username'])


@http_bp.route('/create_room', methods=['POST'])
def create_room_http():
    """Tạo phòng qua HTTP"""
    if 'username' not in session:
        return jsonify({'success': False, 'message': 'Chưa đăng nhập.'}), 401

    data = request.get_json() or request.form
    room_id = (data.get('room_id') or '').strip()
    if not room_id:
        return jsonify({'success': False, 'message': 'room_id không hợp lệ.'}), 400

    username = session['username']
    room = game_logic.create_new_room(room_id, None, None)
    if room is None:
        return jsonify({'success': False, 'message': 'Phòng đã tồn tại.'}), 409

    try:
        socketio.emit('room_list_updated', game_logic.get_room_list(), broadcast=True)
    except Exception:
        pass

    return jsonify({'success': True, 'room_id': room_id})

@http_bp.route('/game/<room_id>')
def game_room(room_id):
    """Trang chơi game"""
    if 'username' not in session:
        return redirect(url_for('http_bp.index')) # Sửa url_for
    
    room = game_logic.get_room(room_id)
    if not room:
        return redirect(url_for('http_bp.lobby')) # Sửa url_for
        
    return render_template('game.html', room_id=room_id, username=session['username'])

@http_bp.route('/scoreboard')
def scoreboard():
    """Trang bảng điểm"""
    return render_template('scoreboard.html')


@http_bp.route('/media/<path:filename>')
def media(filename):
    """Phục vụ ảnh/video"""
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__)))
    ext = filename.split('.')[-1].lower()
    VIDEO_EXTS = (
        'mp4', 'webm', 'ogg', 'avi', 'mov', 'mkv', 'flv', 'm4v', '3gp', 'wmv', 'vob', 'mpg', 'mpeg'
    )
    media_type = 'videos' if ext in VIDEO_EXTS else 'images'
    media_dir = os.path.abspath(os.path.join(base_dir, '..', '..', 'statics', media_type))
    return send_from_directory(media_dir, filename)


@http_bp.route('/admin/questions', methods=['GET'])
def admin_questions():
    """Form upload câu hỏi"""
    if 'username' not in session:
        return redirect(url_for('http_bp.index')) # Sửa url_for
    try:
        from source.server import game_logic
        questions = game_logic.QUESTIONS
    except Exception:
        questions = []
    return render_template('admin_questions.html', questions=questions)


@http_bp.route('/admin/questions/upload', methods=['POST'])
def upload_question():
    """Xử lý upload câu hỏi"""
    if 'username' not in session:
        return redirect(url_for('http_bp.index')) # Sửa url_for

    media_type = request.form.get('mediaType')
    file = request.files.get('mediaFile')
    prompt = request.form.get('prompt', '').strip()
    answer = request.form.get('answer', '').strip()

    if not prompt or not answer:
        return jsonify({'success': False, 'message': 'Vui lòng nhập câu hỏi và đáp án.'})

    if media_type in ['image', 'video'] and (not file or file.filename == ''):
        return jsonify({'success': False, 'message': 'Vui lòng chọn file media.'})

    filename = None
    if file and file.filename:
        filename = secure_filename(file.filename)
        detected_type = 'video' if (file.mimetype and file.mimetype.startswith('video')) else 'image'
        media_folder = 'videos' if detected_type == 'video' else 'images'
        
        base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__)))
        media_dir = os.path.abspath(os.path.join(base_dir, '..', '..', 'statics', media_folder))
        
        pathlib.Path(media_dir).mkdir(parents=True, exist_ok=True)
        save_path = os.path.join(media_dir, filename)
        file.save(save_path)
        media_type = detected_type

    from source.server import game_logic
    ok = game_logic.add_question_to_file(filename, answer, prompt, media_type)

    if ok:
        game_logic.load_questions_from_file()
        return jsonify({'success': True, 'message': 'Upload thành công.'})
    else:
        return jsonify({'success': False, 'message': 'Lỗi khi lưu metadata.'})
