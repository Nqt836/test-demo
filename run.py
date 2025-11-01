import os
from source.server import create_app, socketio

# Khởi tạo ứng dụng bằng Application Factory
app = create_app()

if __name__ == '__main__':
    # Dùng socketio.run để chạy cả Flask và SocketIO
    port = int(os.environ.get('PORT', 5000))
    socketio.run(app, debug=True, host='127.0.0.1', port=port, use_reloader=False)
