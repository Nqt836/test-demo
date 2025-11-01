document.addEventListener('DOMContentLoaded', () => {
    const socket = io(); // Kết nối tới Socket.IO server

    const roomListEl = document.getElementById('room-list');
    const createRoomForm = document.getElementById('create-room-form');
    const roomIdInput = document.getElementById('room-id');
    const msgEl = document.getElementById('lobby-msg');

    // 1. Yêu cầu danh sách phòng khi vừa vào sảnh
    socket.emit('request_room_list');

    // 2. Lắng nghe sự kiện cập nhật danh sách phòng
    socket.on('room_list_updated', (rooms) => {
        roomListEl.innerHTML = ''; // Xóa danh sách cũ
        if (rooms.length === 0) {
            roomListEl.innerHTML = '<p>Chưa có phòng nào. Hãy tạo một phòng!</p>';
            return;
        }

        rooms.forEach(room => {
            const roomEl = document.createElement('div');
            roomEl.className = 'room-item';
            roomEl.innerHTML = `
                <span><strong>${room.id}</strong> (Chủ phòng: ${room.host})</span>
                <span>${room.count} người</span>
                <button data-room-id="${room.id}">Tham gia</button>
            `;
            roomListEl.appendChild(roomEl);
        });
    });

    // 3. Xử lý khi bấm nút "Tham gia"
    roomListEl.addEventListener('click', (e) => {
        if (e.target.tagName === 'BUTTON') {
            const roomId = e.target.dataset.roomId;
            socket.emit('join_room', { room_id: roomId });
        }
    });

    // 4. Xử lý khi "Tạo phòng" — dùng HTTP để tạo phòng trước khi chuyển trang
    createRoomForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        const roomId = roomIdInput.value.trim();
        if (!roomId) return;

        // Gọi endpoint /create_room
        const resp = await fetch('/create_room', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ room_id: roomId })
        });
        const data = await resp.json();
        if (data.success) {
            // Tạo phòng thành công -> chuyển sang trang game
            window.location.href = `/game/${data.room_id}`;
        } else {
            msgEl.textContent = data.message || 'Lỗi khi tạo phòng.';
            msgEl.className = 'message error';
        }
    });

    // 5. Lắng nghe các sự kiện phản hồi
    socket.on('room_created', (data) => {
        // Tạo phòng thành công -> chuyển sang trang game
        window.location.href = `/game/${data.room_id}`;
    });

    socket.on('joined_room', (data) => {
        // Tham gia phòng thành công -> chuyển sang trang game
        window.location.href = `/game/${data.room_id}`;
    });

    socket.on('error', (data) => {
        msgEl.textContent = data.message;
        msgEl.className = 'message error';
    });

    socket.on('connect_error', () => {
        msgEl.textContent = 'Mất kết nối tới máy chủ.';
        msgEl.className = 'message error';
    });

});