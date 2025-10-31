import random
import time
import os
import json
import csv

# Giải pháp lưu trữ câu hỏi: load từ file CSV ở top-level `statics/questions_output.csv`.
# Mỗi mục có: {"id": 1, "prompt": "...", "answer": "...", "media": "filename.jpg", "type": "image"}

# Đường dẫn tới file questions_output.csv (project_root/statics/questions_output.csv)
_THIS_DIR = os.path.abspath(os.path.dirname(__file__))
_QUESTIONS_CSV = os.path.abspath(os.path.join(_THIS_DIR, '..', '..', 'statics', 'questions_output.csv'))

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

# Biến toàn cục để lưu trạng thái của tất cả các phòng
# Key: room_id, Value: thông tin phòng
game_rooms = {}

class GameRoom:
    """Đại diện cho một phòng chơi"""
    def __init__(self, room_id, host_id=None, host_name=None):
        self.room_id = room_id
        self.host_id = host_id
        # Nếu host_id truyền None -> tạo phòng rỗng (chỉ metadata), người chơi sẽ được thêm khi họ join
        if host_id is not None:
            self.players = {host_id: {"name": host_name, "score": 0}}
        else:
            self.players = {}
        self.game_started = False
        self.current_round = 0
        self.max_rounds = 10
        self.current_question = None
        self.answered_this_round = set() # Lưu SID của người đã trả lời đúng
        self.answer_history = []  # Lưu các câu trả lời (đúng/sai) trong phòng
        # Pool các chỉ số câu hỏi chưa được dùng trong phòng này. Khi rỗng, sẽ refill (shuffle) lại.
        self.remaining_question_indices = []

    def add_player(self, player_id, player_name):
        """Thêm người chơi mới vào phòng"""
        # Nếu phòng hiện đang trống, gán lại host cho người tham gia trước tiên
        if len(self.players) == 0:
            self.host_id = player_id

        if player_id not in self.players:
            self.players[player_id] = {"name": player_name, "score": 0}
            return True
        return False

    def remove_player(self, player_id):
        """Xóa người chơi khi họ ngắt kết nối"""
        if player_id in self.players:
            del self.players[player_id]

    def get_player_list(self):
        """Lấy danh sách người chơi và điểm số"""
        return [p for p in self.players.values()]
    
    def start_game(self):
        """Bắt đầu game, reset điểm và bắt đầu vòng 1"""
        print(f"Starting game in room {self.room_id} with {len(self.players)} players")
        if not self.game_started:
            self.game_started = True
            self.current_round = 0
            for player in self.players.values():
                player["score"] = 0
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
        if filename:
            media_url = f"/media/{filename}"
            media_type = self.current_question.get('type', 'image')
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
    for r in game_rooms.values():
        if r.game_started:
            continue
        count = len(r.players)
        # Nếu không có người chơi trong phòng, host có thể không có trong dict players
        host_name = None
        if hasattr(r, 'host_id') and r.host_id in r.players:
            host_name = r.players[r.host_id]['name']
        else:
            host_name = '---'

        rooms.append({"id": r.room_id, "host": host_name, "count": count})

    return rooms

def create_new_room(room_id, host_id, host_name):
    """Tạo một phòng mới"""
    # host_id/host_name có thể là None nếu tạo phòng qua HTTP (chưa có socket SID)
    if room_id in game_rooms:
        return None
    room = GameRoom(room_id, host_id, host_name)
    game_rooms[room_id] = room
    return room

def get_room(room_id):
    """Lấy thông tin phòng bằng ID"""
    return game_rooms.get(room_id)

def remove_player_from_room(player_id):
    """Tìm và xóa người chơi khỏi bất kỳ phòng nào họ đang ở"""
    room_to_remove_from = None
    player_name = ""
    
    for room in game_rooms.values():
        if player_id in room.players:
            player_name = room.players[player_id]["name"]
            room.remove_player(player_id)
            room_to_remove_from = room
            break

    if room_to_remove_from:
        # Nếu phòng trống, xóa phòng
        if len(room_to_remove_from.players) == 0:
            # Không xóa phòng ngay lập tức để tránh trường hợp reload trang (disconnect) rồi reconnect
            # Trả về room_id và danh sách rỗng; front-end có thể hiển thị phòng và client sẽ join lại.
            # (Nâng cao: có thể đặt timeout để xóa phòng sau vài giây nếu vẫn rỗng.)
            return (room_to_remove_from.room_id, [], player_name)
        
        # Nếu chủ phòng rời đi, chỉ định chủ phòng mới
        if player_id == room_to_remove_from.host_id:
            new_host_id = next(iter(room_to_remove_from.players))
            room_to_remove_from.host_id = new_host_id
            
        return (room_to_remove_from.room_id, room_to_remove_from.get_player_list(), player_name)
    
    return (None, None, None)