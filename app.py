from flask import Flask, render_template, jsonify
from flask_cors import CORS
from flask_socketio import SocketIO, emit
import pandas as pd
import time
import threading

app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret'
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*")

csv_data = []
current_index = 0
is_playing = False
playback_thread = None

def load_csv_data():
    """Загружает данные из CSV-файла."""
    global csv_data
    print("📂 Загрузка CSV-файла...")
    try:
        df = pd.read_csv('data/smart_home_dataset.csv')
        csv_data = df.to_dict('records')
        print(f"✅ Загружено {len(csv_data)} записей.")
        if len(csv_data) > 0:
            print(f"   Пример записи: {csv_data[0].keys()}")
        return True
    except Exception as e:
        print(f"❌ Ошибка загрузки CSV: {e}")
        return False

def playback_loop():
    """Фоновый поток для отправки данных."""
    global current_index, is_playing, csv_data

    print("▶️ Поток воспроизведения ЗАПУЩЕН.")
    while is_playing and current_index < len(csv_data):
        record = csv_data[current_index]
        
        # Отправляем данные в правильном формате
        data_to_emit = {
            'datetime': record.get('Datetime', ''),
            'datetime_short': record.get('Datetime', '')[5:16],  # "MM-DD HH:MM"
            'energy': record.get('Energy Consumption (kWh)', 0),
            'progress': (current_index + 1) / len(csv_data) * 100,
            'total': len(csv_data),
            'current': current_index + 1,
            'television': record.get('Television', 0),
            'dryer': record.get('Dryer', 0),
            'oven': record.get('Oven', 0),
            'refrigerator': record.get('Refrigerator', 0),
            'microwave': record.get('Microwave', 0)
        }
        
        print(f"📤 Отправка {current_index + 1}/{len(csv_data)}: {data_to_emit['datetime_short']} -> {data_to_emit['energy']} кВт·ч")
        
        socketio.emit('new_data', data_to_emit)
        
        current_index += 1
        
        # Задержка между записями
        if current_index < len(csv_data):
            time_diff = csv_data[current_index]['Unix Timestamp'] - record['Unix Timestamp']
            delay = max(0.2, min(time_diff, 2.0))
            time.sleep(delay)

    print("✅ Воспроизведение ЗАВЕРШЕНО.")
    socketio.emit('playback_finished', {'message': 'All data sent'})
    is_playing = False

def start_playback():
    """Запускает воспроизведение."""
    global is_playing, playback_thread, current_index
    if is_playing:
        return
    if current_index >= len(csv_data):
        current_index = 0
    is_playing = True
    playback_thread = threading.Thread(target=playback_loop)
    playback_thread.daemon = True
    playback_thread.start()
    print("🎬 Воспроизведение запущено")

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/status')
def status():
    total = len(csv_data)
    progress = (current_index / total * 100) if total > 0 else 0
    return jsonify({
        'is_playing': is_playing,
        'progress': progress,
        'total': total,
        'current': current_index
    })

@app.route('/api/data')
def get_initial_data():
    """Возвращает первые 100 записей для начального графика."""
    if not csv_data:
        return jsonify([])
    return jsonify(csv_data[:100])

@socketio.on('connect')
def handle_connect():
    print("🔌 Клиент подключился")
    if csv_data and not is_playing:
        start_playback()

@socketio.on('disconnect')
def handle_disconnect():
    print("🔌 Клиент отключился")

if __name__ == '__main__':
    print("="*50)
    print("ЗАПУСК СЕРВЕРА УМНОГО ДОМА")
    print("="*50)
    
    if load_csv_data():
        print(f"\n🌐 Откройте: http://localhost:5000")
        print("⏳ Данные начнут поступать автоматически")
    else:
        print("\n❌ Ошибка загрузки данных")
        exit(1)

    socketio.run(app, host='0.0.0.0', port=5000, debug=True)