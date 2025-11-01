from flask import session, request
from flask_socketio import emit, join_room, leave_room, send

from source.server.extensions import socketio # Import từ extensions
import source.server.game_logic as game_logic

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
    """Khi người dùng ngắt kết nối"""
    username = session.get('username', 'Guest')
    print(f"{username} đã ngắt kết nối (SID: {request.sid})")
    
    room_id, updated_players, player_name = game_logic.remove_player_from_room(request.sid)
    
    if room_id:
        emit('player_left', {
            'message': f'{player_name} đã rời phòng.',
            'players': updated_players
        }, to=room_id)
        emit('room_list_updated', game_logic.get_room_list(), skip_sid=request.sid)

@socketio.on('request_room_list')
def on_request_room_list():
    """Khi người dùng ở sảnh chờ yêu cầu danh sách phòng"""
    emit('room_list_updated', game_logic.get_room_list())


def _find_player_sid_by_name(room, username):
    """Helper: trả về SID nếu người chơi với username đã có trong room"""
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
        emit('room_list_updated', game_logic.get_room_list(), skip_sid=request.sid)
    else:
        emit('error', {'message': f'Phòng "{room_id}" đã tồn tại.'})

@socketio.on('join_room')
def on_join_room(data):
    """Khi người dùng tham gia một phòng có sẵn"""
    room_id = data['room_id']
    username = session['username']
    room = game_logic.get_room(room_id)

    if room:
        # Xử lý reconnect
        existing_sid = _find_player_sid_by_name(room, username)
        if existing_sid:
            pdata = room.players.pop(existing_sid)
            room.players[request.sid] = pdata
            if room.host_id == existing_sid:
                room.host_id = request.sid

            join_room(room_id)
            print(f"User {username} reconnected to room {room_id} (old SID {existing_sid} -> new SID {request.sid})")
            emit('joined_room', {'room_id': room_id})
            emit('player_joined', {
                'message': f'{username} đã (re)kết nối.',
                'players': room.get_player_list(),
                'host_id': room.host_id,
                'my_id': request.sid
            }, to=room_id)
            emit('room_list_updated', game_logic.get_room_list(), skip_sid=request.sid)
            return

        # Không cho join nếu game đã bắt đầu (chỉ cho reconnect)
        if room.game_started:
            emit('error', {'message': 'Phòng đã bắt đầu chơi.'})
            return

        # Join mới
        join_room(room_id)
        room.add_player(request.sid, username)

        print(f"User {username} joined room {room_id}")

        emit('joined_room', {'room_id': room_id})
        emit('player_joined', {
            'message': f'{username} đã tham gia phòng.',
            'players': room.get_player_list(),
            'host_id': room.host_id,
            'my_id': request.sid
        }, to=room_id)

        emit('room_list_updated', game_logic.get_room_list(), skip_sid=request.sid)
    else:
        emit('error', {'message': 'Phòng không tồn tại.'})

@socketio.on('send_chat_message')
def on_chat_message(data):
    """Xử lý chat chung trong phòng"""
    room_id = data['room_id']
    message = data['message']
    username = session.get('username', 'Guest')
    emit('chat_message', {'sender': username, 'message': message}, to=room_id)

@socketio.on('lobby_chat')
def on_lobby_chat(data):
    """Xử lý chat trong sảnh chờ - broadcast cho tất cả người chơi ở sảnh"""
    message = data['message']
    username = session.get('username', 'Guest')
    # Broadcast tới tất cả (skip sender để không nhận lại)
    emit('lobby_chat', {'sender': username, 'message': message}, skip_sid=request.sid)
    # Gửi lại cho sender để xác nhận
    emit('lobby_chat', {'sender': username, 'message': message})

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
        socketio.emit('new_round', round_data, to=room_id)
        socketio.emit('room_list_updated', game_logic.get_room_list(), skip_sid=request.sid)
        
@socketio.on('submit_answer')
def on_submit_answer(data):
    """Khi người chơi gửi câu trả lời"""
    room_id = data['room_id']
    answer = data['answer']
    room = game_logic.get_room(room_id)
    
    if not room or not room.game_started:
        return # Bỏ qua nếu game chưa bắt đầu

    # Xử lý reconnect (nếu SID bị thay đổi)
    if request.sid not in room.players:
        username = session.get('username')
        existing_sid = _find_player_sid_by_name(room, username) if username else None
        if existing_sid:
            pdata = room.players.pop(existing_sid)
            room.players[request.sid] = pdata
            if room.host_id == existing_sid:
                room.host_id = request.sid
        else:
            emit('error', {'message': 'Bạn không có trong phòng.'})
            return

    result = room.check_answer(request.sid, answer)
    player_name = room.players.get(request.sid, {}).get('name', 'Unknown')

    # Gửi thông báo kết quả
    if result['status'] == 'correct_first':
        emit('answer_result', {
            'message': f"🎉 {result['player_name']} là người đầu tiên trả lời đúng!",
            'scores': result['scores']
        }, to=room_id)
        
        # Tự động chuyển vòng mới
        socketio.sleep(5) # set sau 5s sẽ tự động chuyển sang câu hỏi tiếp theo (có thể thay đổi thời gian nếu muốn, sau khi người chơi trả lời đúng)
        next_round_data = room.next_round()
        if next_round_data.get('status') == 'game_over':
            emit('game_over', next_round_data, to=room_id)
        else:
            emit('new_round', next_round_data, to=room_id)
            
    elif result['status'] == 'correct':
        # Thông báo khi người khác cũng trả lời đúng (không cần chat)
        pass
        
    elif result['status'] == 'incorrect':
        # Không hiển thị câu trả lời sai ở chat
        pass