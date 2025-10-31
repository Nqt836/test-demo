import os
from flask import Flask, render_template, request, redirect, url_for, session, jsonify, send_from_directory
from werkzeug.utils import secure_filename
import pathlib
from flask_socketio import SocketIO, emit, join_room, leave_room, send
from flask_sqlalchemy import SQLAlchemy
import eventlet # Cần cho gunicorn

# Import các module logic
from source.server.models import db, User
from source.server.auth import register_user, login_user
import source.server.game_logic as game_logic

# Cấu hình đường dẫn tuyệt đối cho CSDL
base_dir = os.path.abspath(os.path.dirname(__file__))
db_path = os.path.join(base_dir, '..', '..', 'users.db')

# Khởi tạo ứng dụng Flask
app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-very-secret-key-12345'
app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{db_path}'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Khởi tạo DB và SocketIO
db.init_app(app)
socketio = SocketIO(app, async_mode='eventlet')

# Tạo CSDL nếu chưa tồn tại
with app.app_context():
    db.create_all()

# --- Các tuyến đường HTTP (Auth & Lobby) ---

@app.route('/')
def index():
    """Trang đăng nhập/đăng ký"""
    if 'username' in session:
        return redirect(url_for('lobby'))
    return render_template('index.html')

@app.route('/login', methods=['POST'])
def handle_login():
    """Xử lý form đăng nhập"""
    data = request.json
    user = login_user(data['username'], data['password'])
    if user:
        session['username'] = user.username
        session['user_id'] = user.id
        return jsonify({"success": True, "message": "Đăng nhập thành công!"})
    return jsonify({"success": False, "message": "Sai tên đăng nhập hoặc mật khẩu."})

@app.route('/register', methods=['POST'])
def handle_register():
    """Xử lý form đăng ký"""
    data = request.json
    success, message = register_user(data['username'], data['password'])
    return jsonify({"success": success, "message": message})

@app.route('/logout')
def logout():
    session.pop('username', None)
    session.pop('user_id', None)
    return redirect(url_for('index'))

@app.route('/lobby')
def lobby():
    """Sảnh chờ"""
    if 'username' not in session:
        return redirect(url_for('index'))
    return render_template('lobby.html', username=session['username'])


@app.route('/create_room', methods=['POST'])
def create_room_http():
    """Tạo phòng qua HTTP để tránh race condition khi client chuyển trang và socket disconnect.

    Yêu cầu: JSON body {"room_id": "roomname"} hoặc form-encoded.
    Trả về JSON {success: bool, room_id/message}
    """
    if 'username' not in session:
        return jsonify({'success': False, 'message': 'Chưa đăng nhập.'}), 401

    data = request.get_json() or request.form
    room_id = (data.get('room_id') or '').strip()
    if not room_id:
        return jsonify({'success': False, 'message': 'room_id không hợp lệ.'}), 400

    username = session['username']
    # Tạo phòng mà chưa gán host (host sẽ join sau khi client kết nối socket mới)
    room = game_logic.create_new_room(room_id, None, None)
    if room is None:
        return jsonify({'success': False, 'message': 'Phòng đã tồn tại.'}), 409

    # Phát cập nhật danh sách phòng tới mọi client ở sảnh (nếu socket vẫn chạy)
    try:
        socketio.emit('room_list_updated', game_logic.get_room_list(), broadcast=True)
    except Exception:
        pass

    return jsonify({'success': True, 'room_id': room_id})

@app.route('/game/<room_id>')
def game_room(room_id):
    """Trang chơi game"""
    if 'username' not in session:
        return redirect(url_for('index'))
    
    room = game_logic.get_room(room_id)
    if not room:
        # Nếu phòng không tồn tại, quay về sảnh
        return redirect(url_for('lobby'))
        
    return render_template('game.html', room_id=room_id, username=session['username'])

@app.route('/scoreboard')
def scoreboard():
    """Trang bảng điểm (hiển thị tạm thời)"""
    # Dữ liệu bảng điểm thực tế sẽ được gửi qua WebSocket
    return render_template('scoreboard.html')


@app.route('/media/<path:filename>')
def media(filename):
    """Phục vụ ảnh/video từ thư mục statics/{images,videos} ở root project.
    Hỗ trợ nhiều định dạng video phổ biến.
    """
    ext = filename.split('.')[-1].lower()
    VIDEO_EXTS = (
        'mp4', 'webm', 'ogg', 'avi', 'mov', 'mkv', 'flv', 'm4v', '3gp', 'wmv', 'vob', 'mpg', 'mpeg'
    )
    media_type = 'videos' if ext in VIDEO_EXTS else 'images'
    media_dir = os.path.abspath(os.path.join(base_dir, '..', '..', 'statics', media_type))
    return send_from_directory(media_dir, filename)


@app.route('/admin/questions', methods=['GET'])
def admin_questions():
    """Form đơn giản để upload ảnh/video và nhập prompt + answer."""
    if 'username' not in session:
        return redirect(url_for('index'))
    # Lấy danh sách câu hỏi hiện có để hiển thị
    try:
        from source.server import game_logic
        questions = game_logic.QUESTIONS
    except Exception:
        questions = []
    return render_template('admin_questions.html', questions=questions)


@app.route('/admin/questions/upload', methods=['POST'])
def upload_question():
    if 'username' not in session:
        return redirect(url_for('index'))

    media_type = request.form.get('mediaType')
    file = request.files.get('mediaFile')
    prompt = request.form.get('prompt', '').strip()
    answer = request.form.get('answer', '').strip()

    if not prompt or not answer:
        return jsonify({'success': False, 'message': 'Vui lòng nhập câu hỏi và đáp án.'})

    # Nếu là loại câu hỏi có media, yêu cầu file
    if media_type in ['image', 'video'] and (not file or file.filename == ''):
        return jsonify({'success': False, 'message': 'Vui lòng chọn file media.'})

    filename = None
    if file and file.filename:
        filename = secure_filename(file.filename)
        # Determine actual media type from uploaded file's MIME type
        detected_type = 'video' if (file.mimetype and file.mimetype.startswith('video')) else 'image'
        # Save into the appropriate folder based on detected_type
        media_folder = 'videos' if detected_type == 'video' else 'images'
        media_dir = os.path.abspath(os.path.join(base_dir, '..', '..', 'statics', media_folder))
        pathlib.Path(media_dir).mkdir(parents=True, exist_ok=True)
        save_path = os.path.join(media_dir, filename)
        file.save(save_path)
        # override media_type with detected_type so metadata matches actual file
        media_type = detected_type

    # Ghi metadata vào questions.json thông qua game_logic helper
    from source.server import game_logic
    ok = game_logic.add_question_to_file(filename, answer, prompt, media_type)

    if ok:
        # Reload questions để cập nhật bộ nhớ
        game_logic.load_questions_from_file()
        return jsonify({'success': True, 'message': 'Upload thành công.'})
    else:
        return jsonify({'success': False, 'message': 'Lỗi khi lưu metadata.'})


# --- Các trình xử lý sự kiện SocketIO (Real-time) ---

@socketio.on('connect')
def handle_connect():
    """Khi người dùng kết nối WebSocket"""
    if 'username' not in session:
        emit('error', {'message': 'Bạn chưa đăng nhập.'})
        return False # Từ chối kết nối
    print(f"Client connected: {session['username']} (SID: {request.sid})")
    emit('connected', {'message': 'Kết nối thành công!'})

@socketio.on('disconnect')
def handle_disconnect():
    """Khi người dùng ngắt kết nối (tắt tab, mất mạng)"""
    username = session.get('username', 'Guest')
    print(f"Client disconnected: {username} (SID: {request.sid})")
    
    # Kiểm tra xem người chơi có trong phòng không
    room_id, updated_players, player_name = game_logic.remove_player_from_room(request.sid)
    
    if room_id and updated_players:
        # Chỉ gửi thông báo player_left nếu phòng vẫn còn người chơi khác
        emit('player_left', {
            'message': f'{player_name} đã rời phòng.',
            'players': updated_players
        }, to=room_id)
        # Cập nhật lại danh sách phòng ở sảnh
        emit('room_list_updated', game_logic.get_room_list(), broadcast=True)

@socketio.on('request_room_list')
def on_request_room_list():
    """Khi người dùng ở sảnh chờ yêu cầu danh sách phòng"""
    emit('room_list_updated', game_logic.get_room_list())


def _find_player_sid_by_name(room, username):
    """Helper: trả về SID nếu người chơi với username đã có trong room (dựa trên tên).

    Dùng để xử lý reconnect khi SID thay đổi (trong trường hợp tab reload).
    """
    for sid, pdata in room.players.items():
        if pdata.get('name') == username:
            return sid
    return None

@socketio.on('create_room')
def on_create_room(data):
    """Khi người dùng tạo phòng mới"""
    room_id = data['room_id']
    username = session['username']
    
    room = game_logic.create_new_room(room_id, request.sid, username)
    
    if room:
        join_room(room_id)
        print(f"User {username} created and joined room {room_id}")
        emit('room_created', {'room_id': room_id})
        # Cập nhật danh sách phòng cho mọi người ở sảnh
        emit('room_list_updated', game_logic.get_room_list(), broadcast=True)
    else:
        emit('error', {'message': f'Phòng "{room_id}" đã tồn tại.'})

@socketio.on('join_room')
def on_join_room(data):
    """Khi người dùng tham gia một phòng có sẵn"""
    room_id = data['room_id']
    username = session['username']
    room = game_logic.get_room(room_id)

    if room:
        # Nếu user đã có trong room (theo tên) -> đây là reconnect (SID thay đổi)
        existing_sid = _find_player_sid_by_name(room, username)
        if existing_sid:
            # Thay SID cũ bằng SID mới để giữ nguyên điểm và vị trí
            pdata = room.players.pop(existing_sid)
            room.players[request.sid] = pdata
            # Nếu người rời là host, gán host mới
            if room.host_id == existing_sid:
                room.host_id = request.sid

            join_room(room_id)
            print(f"User {username} reconnected to room {room_id} (old SID {existing_sid} -> new SID {request.sid})")
            emit('joined_room', {'room_id': room_id})
            # Không gửi player_joined thông báo cho reconnect
            emit('room_list_updated', game_logic.get_room_list(), broadcast=True)
            return

        # Nếu game đã bắt đầu thì không cho người mới join (trừ trường hợp reconnect handled trên)
        if room.game_started:
            emit('error', {'message': 'Phòng đã bắt đầu chơi.'})
            return

        # Bình thường: join mới
        join_room(room_id)
        room.add_player(request.sid, username)

        print(f"User {username} joined room {room_id}")

        # Gửi sự kiện 'joined_room' chỉ cho người vừa tham gia
        emit('joined_room', {'room_id': room_id})

        # Gửi thông báo và danh sách người chơi cập nhật cho MỌI NGƯỜI trong phòng
        emit('player_joined', {
            'message': f'{username} đã tham gia phòng.',
            'players': room.get_player_list(),
            'host_id': room.host_id,
            'my_id': request.sid
        }, to=room_id)

        # Cập nhật danh sách phòng ở sảnh
        emit('room_list_updated', game_logic.get_room_list(), broadcast=True)
    else:
        emit('error', {'message': 'Phòng không tồn tại.'})

@socketio.on('send_chat_message')
def on_send_chat_message(data):
    """Xử lý tin nhắn chat ở phòng chờ"""
    room_id = data.get('room_id')
    message = data.get('message', '').strip()
    
    if not room_id or not message:
        return
    
    room = game_logic.get_room(room_id)
    if not room:
        emit('error', {'message': 'Phòng không tồn tại.'})
        return
    
    # Lấy tên người gửi từ danh sách người chơi
    sender_name = 'Unknown'
    for player in room.players.values():
        if player['sid'] == request.sid:
            sender_name = player['name']
            break
    
    # Phát tin nhắn đến tất cả người chơi trong phòng
    emit('receive_chat_message', {
        'sender': sender_name,
        'message': message
    }, to=room_id)

@socketio.on('start_game')
def on_start_game(data):
    """Khi chủ phòng bấm bắt đầu game"""
    room_id = data['room_id']
    room = game_logic.get_room(room_id)
    
    if not room:
        emit('error', {'message': 'Phòng không tồn tại.'})
        return
        
    if request.sid != room.host_id:
        emit('error', {'message': 'Chỉ chủ phòng mới được bắt đầu.'})
        return
    
    if len(room.players) < 2:
        emit('error', {'message': 'Cần ít nhất 2 người để bắt đầu.'})
        return

    # Bắt đầu game và lấy dữ liệu vòng 1
    round_data = room.start_game()
    if round_data:
        print(f"Game started in room {room_id}")
        socketio.emit('new_round', round_data, to=room_id)  # Sử dụng socketio.emit thay vì emit
        # Cập nhật sảnh (phòng này biến mất khỏi danh sách chờ)
        socketio.emit('room_list_updated', game_logic.get_room_list(), broadcast=True)

@socketio.on('submit_answer')
def on_submit_answer(data):
    """Khi người chơi gửi câu trả lời"""
    room_id = data['room_id']
    answer = data['answer']
    room = game_logic.get_room(room_id)
    
    if not room or not room.game_started:
        return # Bỏ qua nếu game chưa bắt đầu

    # Ensure the request.sid is associated with a player in the room.
    if request.sid not in room.players:
        # Try to find existing player by username (reconnect case)
        username = session.get('username')
        existing_sid = _find_player_sid_by_name(room, username) if username else None
        if existing_sid:
            # remap player entry to new SID
            pdata = room.players.pop(existing_sid)
            room.players[request.sid] = pdata
            if room.host_id == existing_sid:
                room.host_id = request.sid
        else:
            # Unknown player for this SID -> ignore
            emit('error', {'message': 'Bạn không có trong phòng.'})
            return

    result = room.check_answer(request.sid, answer)
    player_name = room.players.get(request.sid, {}).get('name', 'Unknown')

    # Gửi thông báo kết quả dựa trên logic
    if result['status'] == 'correct_first':
        # Phát đáp án cho tất cả người chơi
        emit('show_answer', {
            'correct_answer': room.current_question.get('answer', ''),
            'question_text': room.current_question.get('prompt', ''),
            'first_correct_player': result['player_name'],
            'scores': result['scores']
        }, to=room_id)
        
        # Tự động chuyển vòng mới sau 5 giây
        socketio.sleep(5)
        next_round_data = room.next_round()
        if next_round_data.get('status') == 'game_over':
            emit('game_over', next_round_data, to=room_id)
        else:
            emit('new_round', next_round_data, to=room_id)
            
    elif result['status'] == 'correct':
        emit('chat_message', {'sender': 'Hệ thống', 'message': f"👍 {player_name} cũng trả lời đúng!"}, to=room_id)
        
    elif result['status'] == 'incorrect':
        emit('chat_message', {'sender': player_name, 'message': answer}, to=room_id) # Hiển thị câu trả lời sai
    
    # (Bỏ qua 'already_answered' để tránh spam)

@socketio.on('send_chat_message')
def on_chat_message(data):
    """Xử lý chat chung trong phòng (không phải trả lời)"""
    room_id = data['room_id']
    message = data['message']
    username = session.get('username', 'Guest')
    emit('chat_message', {'sender': username, 'message': message}, to=room_id)


# Chạy ứng dụng
if __name__ == '__main__':
    # Chạy create_all() lần đầu tiên
    with app.app_context():
        db.create_all()
    # Dùng socketio.run để chạy cả Flask và SocketIO
    socketio.run(app, debug=True, host='0.0.0.0', port=5000)