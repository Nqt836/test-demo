import random
import time
import os
import csv

# đường dẫn tới file questions_output.csv
_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_QUESTIONS_CSV = os.path.abspath(os.path.join(_THIS_DIR, '..', '..', 'statics', 'questions_output.csv'))

# Đọc câu hỏi từ CSV
QUESTIONS = []

def load_questions_from_file():
    global QUESTIONS
    try:
        if os.path.exists(_QUESTIONS_CSV):
            # Mở file với encoding utf-8-sig để loại bỏ BOM nếu có
            with open(_QUESTIONS_CSV, 'r', encoding='utf-8-sig') as f:
                reader = csv.DictReader(f)
                QUESTIONS = []
                for row in reader:
                    # Strip whitespace từ keys và values
                    cleaned_row = {k.strip(): v.strip() if isinstance(v, str) else v for k, v in row.items()}
                    # Chuyển đổi id sang số nguyên
                    cleaned_row['id'] = int(cleaned_row['id'])
                    QUESTIONS.append(cleaned_row)
        else:
            QUESTIONS = []
    except Exception as e:
        print(f"Error loading questions: {e}")
        import traceback
        traceback.print_exc()
        QUESTIONS = []


def add_question_to_file(media_filename, answer, prompt, media_type='image'):
    """Thêm một câu hỏi mới vào file questions_output.csv (append).

    media_filename: tên file đã lưu vào statics/{images,videos}, hoặc None cho text-only
    answer: văn bản đáp án
    prompt: câu hỏi văn bản
    media_type: loại media ('image', 'video', hoặc 'text')
    """
    try:
        global QUESTIONS
        
        # Tìm ID mới (max ID + 1)
        max_id = 0
        if QUESTIONS:
            max_id = max(int(q['id']) for q in QUESTIONS if 'id' in q)
        new_id = max_id + 1

        # Tạo dòng mới
        new_question = {
            "id": new_id,
            "prompt": prompt,
            "answer": answer,
            "media": media_filename if media_filename else "",
            "type": media_type
        }
        
        # Ghi thêm vào file CSV (append mode)
        os.makedirs(os.path.dirname(_QUESTIONS_CSV), exist_ok=True)
        file_exists = os.path.exists(_QUESTIONS_CSV) and os.path.getsize(_QUESTIONS_CSV) > 0
        
        with open(_QUESTIONS_CSV, 'a', newline='', encoding='utf-8') as f:
            fieldnames = ['id', 'prompt', 'answer', 'media', 'type']
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            
            # Nếu file mới tạo, viết header
            if not file_exists:
                writer.writeheader()
            
            writer.writerow(new_question)

        # Cập nhật QUESTIONS trong bộ nhớ
        QUESTIONS.append(new_question)
        return True
    except Exception as e:
        print(f"Error adding question: {e}")
        return False

# Load questions khi import module
load_questions_from_file()

from source.server.models import Room, Player, User
from source.server.extensions import db

class GameRoom:
    """Đại diện cho một phòng chơi"""
    def __init__(self, room_id, host_id=None, host_name=None):
        # Kiểm tra xem phòng đã tồn tại trong DB chưa
        room = Room.query.filter_by(room_id=room_id).first()
        
        if room is None and host_id is not None:
            # Tạo phòng mới trong database
            user = User.query.get(host_id)
            if user:
                room = Room(
                    room_id=room_id,
                    host_id=host_id,
                    game_started=False,
                    current_round=0,
                    max_rounds=10
                )
                db.session.add(room)
                
                # Thêm chủ phòng vào danh sách người chơi
                player = Player(
                    room=room,
                    user_id=host_id,
                    score=0,
                    socket_id=host_id  # Socket.IO session ID
                )
                db.session.add(player)
                db.session.commit()
        
        self.room_id = room_id
        self.db_room = room
        self.current_question = None
        self.answered_this_round = set()  # Lưu SID của người đã trả lời đúng
        self.answer_history = []  # Lưu các câu trả lời (đúng/sai) trong phòng
        self.remaining_question_indices = []  # Pool câu hỏi

    def add_player(self, player_id, player_name):
        """Thêm người chơi mới vào phòng"""
        if not self.db_room:
            return False
            
        # Kiểm tra xem người chơi đã có trong phòng chưa
        existing_player = Player.query.filter_by(
            room_id=self.db_room.id,
            socket_id=player_id
        ).first()
        
        if existing_player:
            return False
            
        # Tìm user từ username
        user = User.query.filter_by(username=player_name).first()
        if not user:
            return False
            
        # Thêm người chơi mới
        new_player = Player(
            room=self.db_room,
            user_id=user.id,
            socket_id=player_id,
            score=0
        )
        db.session.add(new_player)
        
        # Nếu phòng trống, set làm host
        if len(self.db_room.players) == 0:
            self.db_room.host_id = user.id
            
        db.session.commit()
        return True

    def remove_player(self, player_id):
        """Xóa người chơi khi họ ngắt kết nối"""
        if not self.db_room:
            return
            
        player = Player.query.filter_by(
            room_id=self.db_room.id,
            socket_id=player_id
        ).first()
        
        if player:
            db.session.delete(player)
            db.session.commit()

    def get_player_list(self):
        """Lấy danh sách người chơi và điểm số"""
        if not self.db_room:
            return []
            
        return [{
            "name": player.user.username,
            "score": player.score
        } for player in self.db_room.players]
    
    def start_game(self):
        """Bắt đầu game, reset điểm và bắt đầu vòng 1"""
        if not self.db_room or self.db_room.game_started:
            return None
            
        print(f"Starting game in room {self.room_id} with {len(self.db_room.players)} players")
        
        self.db_room.game_started = True
        self.db_room.current_round = 0
        
        # Reset điểm số của tất cả người chơi
        for player in self.db_room.players:
            player.score = 0
            # Chuẩn bị pool câu hỏi cho phòng này
            self._reset_question_pool()
            next_round_data = self.next_round()
            print(f"Next round data: {next_round_data}")
            return next_round_data
        print("Game already started")
        return None

    def _reset_question_pool(self):
        """Tạo lại và xáo danh sách chỉ số câu hỏi cho phòng này.

        Khi QUESTIONS thay đổi, gọi lại load_questions_from_file() và phương thức này
        sẽ refill pool cho tất cả phòng mới khi bắt đầu game.
        """
        try:
            total = len(QUESTIONS)
            # Tạo list các chỉ số và xáo
            self.remaining_question_indices = list(range(total))
            random.shuffle(self.remaining_question_indices)
        except Exception:
            self.remaining_question_indices = []

    def next_round(self):
        """Chuẩn bị cho vòng chơi tiếp theo"""
        print(f"Starting next round. Current round: {self.current_round}, Max rounds: {self.max_rounds}")
        if self.current_round >= self.max_rounds:
            return self.end_game()

        # Đảm bảo có câu hỏi để chọn
        if not QUESTIONS:
            print("Warning: No questions available")
            return self.end_game()

        self.current_round += 1
        # Nếu room không có pool (ví dụ start_game chưa gọi), tạo pool tạm thời
        if not self.remaining_question_indices:
            self._reset_question_pool()

        # Lấy chỉ số câu hỏi cuối cùng trong pool (pop để tránh lặp lại)
        q_index = None
        if self.remaining_question_indices:
            q_index = self.remaining_question_indices.pop()
        else:
            # Trường hợp hiếm: không có chỉ số, refill rồi lấy
            self._reset_question_pool()
            if self.remaining_question_indices:
                q_index = self.remaining_question_indices.pop()

        # Nếu vẫn không có chỉ số thì kết thúc game
        if q_index is None:
            print("Warning: No question index available after refill")
            return self.end_game()

        self.current_question = QUESTIONS[q_index]
        self.answered_this_round = set()

        print(f"Selected question (index {q_index}): {self.current_question}")

        # Xác định url và type
        filename = self.current_question.get('media')
        media_type = self.current_question.get('type', 'image')
        
        if filename:
            # Build URL dựa trên media type
            if media_type == 'video':
                media_url = f"/statics/videos/{filename}"
            else:
                media_url = f"/statics/images/{filename}"
        else:
            media_url = None
            media_type = 'text'

        # Trả về dữ liệu cho vòng mới (gồm url media, kiểu và văn bản câu hỏi nếu có)
        return {
            "round": self.current_round,
            "max_rounds": self.max_rounds,
            "media_url": media_url,
            "media_type": media_type,
            "question_text": self.current_question.get('prompt', ''),
            "players": self.get_player_list()
        }

    def check_answer(self, player_id, answer):
        """Kiểm tra câu trả lời của người chơi"""
        if not self.current_question:
            return {"status": "error", "message": "Game chưa bắt đầu"}

        # Chuẩn hóa câu trả lời (viết thường, bỏ dấu cách)
        clean_answer = answer.strip().lower()
        correct_answer = self.current_question['answer'].lower()
        timestamp = time.time()

        # Lưu bản ghi câu trả lời (tạm thời). Sẽ cập nhật field 'correct' sau khi so sánh
        record = {
            'round': self.current_round,
            'player_id': player_id,
            'player_name': self.players.get(player_id, {}).get('name', 'Unknown'),
            'answer': answer,
            'timestamp': timestamp,
            'correct': False
        }

        if clean_answer == correct_answer:
            # Nếu người này chưa trả lời đúng vòng này
            if player_id not in self.answered_this_round:
                self.players[player_id]["score"] += 1
                self.answered_this_round.add(player_id)
                # Đánh dấu record đúng và lưu
                record['correct'] = True
                self.answer_history.append(record)

                # Nếu là người đầu tiên trả lời đúng
                if len(self.answered_this_round) == 1:
                    return {
                        "status": "correct_first",
                        "player_name": self.players[player_id]["name"],
                        "scores": self.get_player_list()
                    }
                else:
                    # Trả lời đúng nhưng không phải đầu tiên
                    return {"status": "correct", "player_name": self.players[player_id]["name"]}
            else:
                # Người này đã trả lời đúng trước đó
                record['correct'] = False
                record['note'] = 'already_answered'
                self.answer_history.append(record)
                return {"status": "already_answered"}
        else:
            # Lưu câu trả lời sai vào lịch sử
            self.answer_history.append(record)
            return {"status": "incorrect", "player_name": self.players[player_id]["name"]}

    def end_game(self):
        """Kết thúc game và trả về bảng xếp hạng"""
        self.game_started = False
        self.current_question = None
        scoreboard = sorted(self.get_player_list(), key=lambda x: x['score'], reverse=True)
        return {"status": "game_over", "scoreboard": scoreboard}

# --- Các hàm quản lý phòng ---

def get_room_list():
    """Lấy danh sách các phòng đang chờ"""
    rooms = []
    db_rooms = Room.query.filter_by(game_started=False).all()
    
    for r in db_rooms:
        count = len(r.players)
        host = User.query.get(r.host_id)
        host_name = host.username if host else '---'
        
        rooms.append({
            "id": r.room_id,
            "host": host_name,
            "count": count
        })
    
    return rooms

def create_new_room(room_id, host_id, host_name):
    """Tạo một phòng mới"""
    # Kiểm tra xem phòng đã tồn tại chưa
    existing_room = Room.query.filter_by(room_id=room_id).first()
    if existing_room:
        return None
        
    room = GameRoom(room_id, host_id, host_name)
    return room

def get_room(room_id):
    """Lấy thông tin phòng bằng ID"""
    room = Room.query.filter_by(room_id=room_id).first()
    if room:
        return GameRoom(room_id)
    return None

def remove_player_from_room(player_id):
    """Tìm và xóa người chơi khỏi bất kỳ phòng nào họ đang ở"""
    player = Player.query.filter_by(socket_id=player_id).first()
    if not player:
        return (None, None, None)
        
    room = player.room
    player_name = player.user.username
    
    # Xóa người chơi khỏi phòng
    db.session.delete(player)
    
    # Nếu phòng trống
    if len(room.players) <= 1:  # 1 vì player hiện tại chưa bị xóa khỏi DB
        # Giữ lại phòng nhưng trả về danh sách rỗng
        db.session.commit()
        return (room.room_id, [], player_name)
    
    # Nếu là chủ phòng rời đi, chỉ định chủ phòng mới
    if player.user_id == room.host_id:
        new_host = room.players[0] if room.players else None
        if new_host:
            room.host_id = new_host.user_id
            db.session.commit()
    
    # Lấy danh sách người chơi còn lại
    player_list = [{
        "name": p.user.username,
        "score": p.score
    } for p in room.players if p.id != player.id]
    
    db.session.commit()
    return (room.room_id, player_list, player_name)