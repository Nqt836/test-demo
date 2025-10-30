document.addEventListener('DOMContentLoaded', () => {
    // Kết nối socket
    const socket = io();

    // Lấy các element trên DOM
    const waitScreen = document.getElementById('wait-screen');
    const gameScreen = document.getElementById('game-screen');
    const playerListEl = document.getElementById('player-list');
    const playerCountEl = document.getElementById('player-count');
    const startGameBtn = document.getElementById('start-game-btn');
    const currentRoundEl = document.getElementById('current-round');
    const maxRoundsEl = document.getElementById('max-rounds');
    const gameImageEl = document.getElementById('game-image');
    const answerResultEl = document.getElementById('answer-result');
    const chatMessagesEl = document.getElementById('chat-messages');
    const answerForm = document.getElementById('answer-form');
    const answerInput = document.getElementById('answer-input');
    const chatForm = document.getElementById('chat-form');
    const chatInput = document.getElementById('chat-input');
    
    let mySid = null; // Biến lưu SID của chính mình

    // --- Hàm trợ giúp ---
    
    // Hàm cập nhật danh sách người chơi
    function updatePlayerList(players) {
        playerListEl.innerHTML = '';
        players.forEach(player => {
            const li = document.createElement('li');
            li.textContent = `${player.name} - ${player.score} điểm`;
            playerListEl.appendChild(li);
        });
        playerCountEl.textContent = players.length;
    }

    // Hàm thêm tin nhắn vào chat
    function addChatMessage(sender, message, type = 'user') {
        const msgEl = document.createElement('p');
        msgEl.innerHTML = `<strong>${sender}:</strong> ${message}`;
        msgEl.className = type; // 'user' hoặc 'system'
        chatMessagesEl.appendChild(msgEl);
        chatMessagesEl.scrollTop = chatMessagesEl.scrollHeight; // Cuộn xuống dưới
    }

    // --- Xử lý Socket ---

    // 0. Khi kết nối thành công, gửi yêu cầu tham gia phòng
    socket.on('connect', () => {
        console.log('Connected! Emitting join_room...');
        // Biến ROOM_ID được lấy từ thẻ <script> trong game.html
        socket.emit('join_room', { room_id: ROOM_ID });
    });

    // 1. Lắng nghe khi có người chơi tham gia/rời đi
    socket.on('player_joined', (data) => {
        addChatMessage('Hệ thống', data.message, 'system-msg');
        updatePlayerList(data.players);
        
        // Lưu SID của mình
        if (data.my_id) {
            mySid = data.my_id;
        }

        // Hiển thị nút "Bắt đầu" nếu mình là chủ phòng
        if (mySid === data.host_id) {
            startGameBtn.style.display = 'block';
        }
    });

    socket.on('player_left', (data) => {
        addChatMessage('Hệ thống', data.message, 'system-msg');
        updatePlayerList(data.players);
    });

    // 1b. Xử lý gửi tin nhắn ở phòng chờ
    chatForm.addEventListener('submit', (e) => {
        e.preventDefault();
        const message = chatInput.value.trim();
        if (message) {
            socket.emit('send_chat_message', { room_id: ROOM_ID, message: message });
            chatInput.value = '';
            chatInput.focus();
        }
    });

    // 1c. Lắng nghe tin nhắn từ người chơi khác
    socket.on('receive_chat_message', (data) => {
        addChatMessage(data.sender, data.message, 'user');
    });

    // 2. Xử lý khi chủ phòng bấm "Bắt đầu Game"
    startGameBtn.addEventListener('click', () => {
        socket.emit('start_game', { room_id: ROOM_ID });
    });

    // 3. Lắng nghe khi có vòng chơi mới
    socket.on('new_round', (data) => {
        console.log('New round received:', data);  // Debug log
        // Ẩn màn hình chờ và hiện màn hình game
        waitScreen.style.display = 'none';
        gameScreen.style.display = 'block';
        answerForm.style.display = 'flex';
        chatForm.style.display = 'none'; // Ẩn chat form khi game bắt đầu

        // Cập nhật thông tin vòng chơi
        currentRoundEl.textContent = data.round;
        maxRoundsEl.textContent = data.max_rounds;
        answerResultEl.textContent = ''; // Xóa kết quả vòng trước
        answerInput.value = ''; // Xóa input
        answerInput.disabled = false;

        // Hiển thị media (ảnh hoặc video) dựa trên media_type
        const mediaUrl = data.media_url || '';
        const mediaType = data.media_type || 'image';
        const gameVideoEl = document.getElementById('game-video');
        const gameImageEl = document.getElementById('game-image');

        // Reset
        gameImageEl.style.display = 'none';
        gameVideoEl.style.display = 'none';
        gameVideoEl.pause();
        gameVideoEl.removeAttribute('src');

        if (mediaType === 'video') {
            // URL-encode filename to avoid issues with spaces or special characters
            const encoded = encodeURI(mediaUrl);
            gameVideoEl.src = encoded;
            gameVideoEl.style.display = 'block';
            // Ensure video fits and can autoplay: mute + playsinline
            try {
                gameVideoEl.muted = true; // required by many browsers for autoplay
                gameVideoEl.autoplay = true;
                gameVideoEl.playsInline = true;
                gameVideoEl.load();
                // Attempt to play; may still be blocked on some browsers, but muted helps
                const p = gameVideoEl.play();
                if (p && p.then) {
                    p.then(() => {
                        // playing
                    }).catch((err) => {
                        console.debug('Video play prevented:', err);
                    });
                }
            } catch (e) {
                console.debug('Video autoplay setup error', e);
            }
        } else {
            gameImageEl.src = mediaUrl;
            gameImageEl.style.display = 'block';
        }

        // Hiển thị câu hỏi dạng text nếu server trả về
        const questionTextEl = document.getElementById('question-text');
        if (questionTextEl) {
            if (data.question_text) {
                questionTextEl.textContent = data.question_text;
                questionTextEl.style.display = 'block';
            } else {
                questionTextEl.textContent = '';
                questionTextEl.style.display = 'none';
            }
        }

        updatePlayerList(data.players);
        addChatMessage('Hệ thống', `--- Vòng ${data.round} bắt đầu! ---`, 'system-msg');
    });

    // 4. Gửi câu trả lời
    answerForm.addEventListener('submit', (e) => {
        e.preventDefault();
        const answer = answerInput.value.trim();
        if (answer) {
            // Phân biệt chat thường và trả lời
            if (answer.startsWith('/chat ')) {
                const chatMsg = answer.substring(6);
                socket.emit('send_chat_message', { room_id: ROOM_ID, message: chatMsg });
            } else {
                // Đây là câu trả lời
                socket.emit('submit_answer', { room_id: ROOM_ID, answer: answer });
            }
            answerInput.value = '';
        }
    });

    // 5. Lắng nghe tin nhắn chat
    socket.on('chat_message', (data) => {
        addChatMessage(data.sender, data.message, (data.sender === 'Hệ thống' ? 'system-msg' : 'user-msg'));
    });

    // 6. Lắng nghe kết quả trả lời
    socket.on('answer_result', (data) => {
        answerResultEl.textContent = data.message;
        updatePlayerList(data.scores);
        // Vô hiệu hóa input nếu trả lời đúng đầu tiên
        answerInput.disabled = true; 
    });

    // 6b. Lắng nghe sự kiện hiển thị đáp án
    socket.on('show_answer', (data) => {
        // Hiển thị đáp án trên màn hình (có thể hiển thị ở answer-result element)
        answerResultEl.innerHTML = `
            <div style="background-color: #d4edda; padding: 15px; border-radius: 5px; text-align: center;">
                <p style="margin: 0; font-weight: bold; color: #155724;">🎉 ${data.first_correct_player} là người đầu tiên trả lời đúng!</p>
                <p style="margin: 10px 0 0 0; font-size: 18px; color: #155724;"><strong>Đáp án:</strong> ${data.correct_answer}</p>
                <p style="margin: 5px 0 0 0; font-size: 14px; color: #666;">Câu hỏi: ${data.question_text}</p>
            </div>
        `;
        updatePlayerList(data.scores);
        // Vô hiệu hóa input sau khi có đáp án
        answerInput.disabled = true;
    });

    // 7. Lắng nghe khi game kết thúc
    socket.on('game_over', (data) => {
        addChatMessage('Hệ thống', 'Game kết thúc! Đang chuyển đến bảng xếp hạng...', 'system-msg');
        
        // Lưu bảng điểm vào localStorage để trang scoreboard.html có thể đọc
        localStorage.setItem('scoreboard', JSON.stringify(data.scoreboard));
        
        // Chuyển trang sau 3 giây
        setTimeout(() => {
            window.location.href = '/scoreboard';
        }, 3000);
    });

    // 8. Bắt lỗi
    socket.on('error', (data) => {
        alert(data.message);
        // Nếu lỗi nghiêm trọng (ví dụ phòng không tồn tại), đá về sảnh
        if (data.message.includes('không tồn tại')) {
            window.location.href = '/lobby';
        }
    });

});