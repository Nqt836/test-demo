document.addEventListener('DOMContentLoaded', function() {
    // Lấy dữ liệu bảng điểm từ localStorage (do game.js lưu)
    const scoreboardData = JSON.parse(localStorage.getItem('scoreboard'));
    const tableBody = document.querySelector('#scoreboard-table tbody');

    if (scoreboardData && tableBody) {
        scoreboardData.forEach((player, index) => {
            const row = tableBody.insertRow();
            row.innerHTML = `
                <td>${index + 1}</td>
                <td>${player.name}</td>
                <td>${player.score}</td>
            `;
        });
    } else {
        tableBody.innerHTML = '<tr><td colspan="3">Không tìm thấy dữ liệu bảng điểm.</td></tr>';
    }

    // Xóa dữ liệu cũ
    localStorage.removeItem('scoreboard');
});