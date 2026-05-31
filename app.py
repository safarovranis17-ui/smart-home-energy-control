from flask import Flask, render_template, jsonify
from flask_cors import CORS
from flask_socketio import SocketIO, emit
import pandas as pd
import time
import threading

# Инициализация приложения
app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret'
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*")

# Глобальные переменные для управления воспроизведением
csv_data = []            # Все данные из CSV
current_index = 0        # Текущая позиция воспроизведения
is_playing = False       # Флаг воспроизведения
playback_thread = None   # Поток для воспроизведения

def load_csv_data():
    """Загружает данные из CSV-файла в глобальный список."""
    global csv_data
    print("📂 Загрузка CSV-файла...")
    try:
        df = pd.read_csv('data/smart_home_dataset.csv')
        # Преобразуем в список словарей для удобства
        csv_data = df.to_dict('records')
        print(f"✅ Загружено {len(csv_data)} записей.")
        print(f"   Период данных: с {csv_data[0]['Datetime']} по {csv_data[-1]['Datetime']}")
        return True
    except FileNotFoundError:
        print("❌ Ошибка: Файл 'data/smart_home_dataset.csv' не найден.")
        return False
    except Exception as e:
        print(f"❌ Ошибка при загрузке CSV: {e}")
        return False

def playback_loop():
    """Фоновый поток, который последовательно отправляет данные всем клиентам."""
    global current_index, is_playing, csv_data

    print("▶️ Поток автоматического воспроизведения ЗАПУЩЕН.")
    while is_playing and current_index < len(csv_data):
        record = csv_data[current_index]
        
        # Формируем пакет для отправки
        data_to_emit = {
            'datetime': record.get('Datetime', ''),
            'energy': record.get('Energy Consumption (kWh)', 0),
            'progress': (current_index + 1) / len(csv_data) * 100,
            'total': len(csv_data),
            'current': current_index + 1
        }
        # Отправляем событие всем подключенным клиентам
        socketio.emit('new_data', data_to_emit)
        
        current_index += 1
        
        # Рассчитываем задержку для следующей отправки
        if current_index < len(csv_data):
            # Разница во времени между текущей и следующей записью (в секундах)
            time_diff = csv_data[current_index]['Unix Timestamp'] - record['Unix Timestamp']
            # Ограничиваем паузу между 0.2 и 3 секундами для плавности
            delay = max(0.2, min(time_diff, 3.0))
            time.sleep(delay)

    print("✅ Автоматическое воспроизведение ЗАВЕРШЕНО.")
    socketio.emit('playback_finished', {'message': 'All data sent'})
    is_playing = False

def start_playback():
    """Запускает поток воспроизведения."""
    global is_playing, playback_thread, current_index
    if is_playing:
        print("Воспроизведение уже идет.")
        return
    if current_index >= len(csv_data):
        current_index = 0  # Начать заново, если дошли до конца
    is_playing = True
    playback_thread = threading.Thread(target=playback_loop)
    playback_thread.daemon = True  # Поток завершится вместе с приложением
    playback_thread.start()

# --- Flask Маршруты (API) ---
@app.route('/')
def index():
    """Главная страница."""
    return render_template('index.html')

@app.route('/api/status')
def status():
    """Возвращает текущий статус воспроизведения."""
    total = len(csv_data)
    progress = (current_index / total * 100) if total > 0 else 0
    return jsonify({
        'is_playing': is_playing,
        'progress': progress,
        'total': total,
        'loaded': len(csv_data) > 0
    })

@app.route('/api/data')
def get_initial_data():
    """Отдает начальную порцию данных (например, первые 100 записей для построения графика)."""
    if not csv_data:
        return jsonify([])
    # Отправляем первые 100 записей, чтобы при загрузке страницы график не был пустым
    return jsonify(csv_data[:100])

# --- WebSocket события ---
@socketio.on('connect')
def handle_connect():
    """Обработчик подключения нового клиента."""
    print("🔌 Клиент подключился. Запускаем воспроизведение...")
    # Как только клиент подключился, автоматически начинаем отправку данных
    if csv_data and not is_playing:
        start_playback()
    elif not csv_data:
        emit('error', {'message': 'Данные не загружены на сервере.'})

@socketio.on('disconnect')
def handle_disconnect():
    """Обработчик отключения клиента."""
    print("🔌 Клиент отключился.")

# --- Точка входа ---
if __name__ == '__main__':
    print("="*50)
    print("ЗАПУСК СЕРВЕРА УМНОГО ДОМА")
    print("="*50)
    
    if load_csv_data():
        print("\n🌐 Веб-интерфейс будет доступен по адресу: http://localhost:5000")
        print("⏳ Как только вы откроете страницу, данные начнут автоматически поступать на график.")
    else:
        print("\n❌ Не удалось загрузить данные. Убедитесь, что файл 'smart_home_dataset.csv' есть в папке 'data'.")
        exit(1)

    socketio.run(app, host='0.0.0.0', port=5000, debug=True)