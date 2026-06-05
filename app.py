from flask import Flask, render_template, jsonify
from flask_cors import CORS
from flask_socketio import SocketIO, emit
import pandas as pd
import numpy as np
import time
import threading
from datetime import datetime

app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret'
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*")

csv_data = []
current_index = 0
is_streaming = False
stream_thread = None

def load_csv_data():
    """Загружает данные из CSV-файла."""
    global csv_data
    print("📂 Загрузка CSV-файла...")
    try:
        df = pd.read_csv('data/smart_home_dataset.csv')
        csv_data = df.to_dict('records')
        print(f"✅ Загружено {len(csv_data)} записей.")
        if len(csv_data) > 0:
            print(f"   Период: {csv_data[0].get('Datetime', 'N/A')} - {csv_data[-1].get('Datetime', 'N/A')}")
        return True
    except Exception as e:
        print(f"❌ Ошибка загрузки CSV: {e}")
        return False

def data_stream_loop():
    """Фоновый поток для передачи данных."""
    global current_index, is_streaming, csv_data

    print("▶️ Поток данных запущен")
    
    while is_streaming and current_index < len(csv_data):
        record = csv_data[current_index]
        
        # Отправляем данные клиентам
        data_to_emit = {
            'datetime': record.get('Datetime', ''),
            'datetime_short': record.get('Datetime', '')[5:16] if record.get('Datetime') else '',
            'energy': round(record.get('Energy Consumption (kWh)', 0), 2),
            'voltage': round(record.get('Voltage', 0), 1),
            'apparent_power': round(record.get('Apparent Power', 0), 1),
            'television': record.get('Television', 0),
            'dryer': record.get('Dryer', 0),
            'oven': record.get('Oven', 0),
            'refrigerator': record.get('Refrigerator', 0),
            'microwave': record.get('Microwave', 0),
            'progress': round((current_index + 1) / len(csv_data) * 100, 1),
            'current': current_index + 1,
            'total': len(csv_data)
        }
        
        socketio.emit('new_data', data_to_emit)
        
        current_index += 1
        
        # Задержка между записями
        if current_index < len(csv_data):
            time_diff = csv_data[current_index]['Unix Timestamp'] - record['Unix Timestamp']
            delay = max(0.1, min(time_diff, 2.0))
            time.sleep(delay)
    
    print("✅ Поток данных завершен")
    socketio.emit('stream_finished', {'message': 'Все данные переданы'})
    is_streaming = False

def start_data_stream():
    """Запускает поток передачи данных."""
    global is_streaming, stream_thread, current_index
    if is_streaming:
        return
    if current_index >= len(csv_data):
        current_index = 0
    is_streaming = True
    stream_thread = threading.Thread(target=data_stream_loop)
    stream_thread.daemon = True
    stream_thread.start()
    print("🎬 Поток данных запущен")

@app.route('/')
def index():
    """Главная страница"""
    return render_template('index.html')

@app.route('/analytics')
def analytics():
    """Страница аналитики и советов по экономии"""
    return render_template('analytics.html')

@app.route('/calculator')
def calculator():
    """Калькулятор сценариев Что, если?"""
    return render_template('calculator.html')

@app.route('/automation')
def automation():
    """Страница автоматизации и рекомендаций"""
    return render_template('automation.html')

@app.route('/api/status')
def get_status():
    """Статус системы"""
    total = len(csv_data)
    progress = round((current_index / total * 100), 1) if total > 0 else 0
    return jsonify({
        'is_streaming': is_streaming,
        'progress': progress,
        'total': total,
        'current': current_index
    })

@app.route('/api/data')
def get_initial_data():
    """Возвращает данные для графиков"""
    if not csv_data:
        return jsonify([])
    # Возвращаем последние 500 записей для производительности
    return jsonify(csv_data[-500:])

@app.route('/api/statistics')
def get_statistics():
    """Возвращает статистику"""
    if not csv_data:
        return jsonify({'avg_energy': 0, 'max_energy': 0, 'min_energy': 0, 'total_records': 0, 'avg_voltage': 230})
    
    energies = [d.get('Energy Consumption (kWh)', 0) for d in csv_data]
    voltages = [d.get('Voltage', 0) for d in csv_data if d.get('Voltage', 0) > 0]
    
    return jsonify({
        'avg_energy': round(sum(energies) / len(energies), 2),
        'max_energy': round(max(energies), 2),
        'min_energy': round(min(energies), 2),
        'avg_voltage': round(sum(voltages) / len(voltages), 1) if voltages else 230,
        'total_records': len(csv_data)
    })

@app.route('/api/amortization')
def get_amortization():
    """Расчет амортизации для аналитики"""
    if len(csv_data) < 50:
        return jsonify({'devices': {}, 'overall': 0, 'status': {'text': 'Недостаточно данных'}})
    
    # Берем последние 500 записей для расчета
    recent = csv_data[-500:]
    
    devices = ['Television', 'Dryer', 'Oven', 'Refrigerator', 'Microwave']
    device_keys = ['television', 'dryer', 'oven', 'refrigerator', 'microwave']
    
    total_energy = sum(d.get('Energy Consumption (kWh)', 0) for d in recent)
    device_stats = {}
    
    for i, device in enumerate(devices):
        key = device_keys[i]
        device_energy = 0
        device_count = 0
        for d in recent:
            if d.get(key, 0) == 1:
                device_energy += d.get('Energy Consumption (kWh)', 0)
                device_count += 1
        
        usage_pct = (device_count / len(recent)) * 100 if recent else 0
        energy_pct = (device_energy / total_energy * 100) if total_energy > 0 else 0
        
        # Расчет амортизации
        if device == 'Refrigerator':
            score = min(100, usage_pct * 0.6 + energy_pct * 0.4)
        elif device == 'Dryer':
            score = min(100, usage_pct * 0.7 + energy_pct * 0.5)
        elif device == 'Oven':
            score = min(100, usage_pct * 0.5 + energy_pct * 0.6)
        else:
            score = min(100, usage_pct * 0.4 + energy_pct * 0.3)
        
        device_stats[device] = {
            'score': round(score, 1),
            'usage': round(usage_pct, 1),
            'energy_pct': round(energy_pct, 1)
        }
    
    overall = sum(device_stats[d]['score'] for d in devices) / len(devices)
    
    def get_status(score):
        if score < 30: return {'text': 'Отличное', 'color': '#4caf50', 'icon': '✅'}
        if score < 50: return {'text': 'Хорошее', 'color': '#8bc34a', 'icon': '🟢'}
        if score < 70: return {'text': 'Удовлетворительное', 'color': '#ffc107', 'icon': '⚠️'}
        return {'text': 'Требует внимания', 'color': '#ff9800', 'icon': '🔴'}
    
    return jsonify({
        'devices': device_stats,
        'overall': round(overall, 1),
        'status': get_status(overall)
    })

@socketio.on('connect')
def handle_connect():
    """Обработчик подключения WebSocket"""
    print("🔌 Клиент подключен")
    if csv_data and not is_streaming:
        start_data_stream()

if __name__ == '__main__':
    print("="*50)
    print("СИСТЕМА УПРАВЛЕНИЯ ЭНЕРГОПОТРЕБЛЕНИЕМ")
    print("Умный дом с предиктивной амортизацией")
    print("="*50)
    
    if load_csv_data():
        print(f"\n🌐 Сервер запущен: http://localhost:5000")
        print("📊 Страницы:")
        print("   - Главная: /")
        print("   - Аналитика: /analytics")
        print("   - Калькулятор: /calculator")
        print("   - Рекомендации: /automation")
    else:
        print("\n❌ Ошибка загрузки данных")
        exit(1)

    socketio.run(app, host='0.0.0.0', port=5000, debug=True)