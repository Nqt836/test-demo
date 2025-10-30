// Xử lý đăng nhập
document.getElementById('login-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    const username = document.getElementById('login-username').value;
    const password = document.getElementById('login-password').value;
    const msgEl = document.getElementById('login-msg');

    const response = await fetch('/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username, password })
    });
    const data = await response.json();
    
    msgEl.textContent = data.message;
    if (data.success) {
        msgEl.className = 'message success';
        window.location.href = '/lobby';
    } else {
        msgEl.className = 'message error';
    }
});

// Xử lý đăng ký
document.getElementById('register-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    const username = document.getElementById('register-username').value;
    const password = document.getElementById('register-password').value;
    const msgEl = document.getElementById('register-msg');
    
    const response = await fetch('/register', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username, password })
    });
    const data = await response.json();

    msgEl.textContent = data.message;
    if (data.success) {
        msgEl.className = 'message success';
    } else {
        msgEl.className = 'message error';
    }
});