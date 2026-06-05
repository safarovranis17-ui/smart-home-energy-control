from flask import Flask, render_template, jsonify
from flask_cors import CORS
from flask_socketio import SocketIO, emit
import pandas as pd
import numpy as np
import time
import threading
from collections import deque
from datetime import datetime

app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret'
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*")

csv_data = []
current_index = 0
is_streaming = False
stream_thread = None

# Данные для накопления статистики (скользящее окно)
historical_window = deque(maxlen=2000)  # последние 2000 записей (~20 дней)
last_amortization_update = 0
amortization_cache = None

# Веса важности приборов
DEVICE_WEIGHTS = {
    'Refrigerator': 0.35,   # Холодильник - самый важный
    'Oven': 0.25,           # Духовка
    'Dryer': 0.20,          # Сушилка
    'Television': 0.15,     # Телевизор
    'Microwave': 0.05       # Микроволновка
}

def load_csv_data():
    global csv_data
    print("📂 Загрузка данных...")
    try:
        df = pd.read_csv('data/smart_home_dataset.csv')
        csv_data = df.to_dict('records')
        print(f"✅ Загружено {len(csv_data)} записей")
        return True
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        return False

def calculate_stable_amortization():
    """
    Рассчитывает стабильную амортизацию на основе накопленной статистики.
    Вызывается периодически, а не для каждой записи.
    """
    if len(historical_window) < 100:
        return None
    
    df = pd.DataFrame(historical_window)
    
    # Берем последние 500 записей для стабильности
    recent = df.tail(500)
    
    # 1. Среднее потребление за период
    avg_energy = recent['energy'].mean()
    max_energy = recent['energy'].max()
    energy_factor = avg_energy / 8.0  # 8 кВт·ч - пиковая нагрузка
    
    # 2. Частота использования каждого прибора (за весь период)
    device_usage = {}
    for device in DEVICE_WEIGHTS.keys():
        device_col = device.lower()
        if device_col in recent.columns:
            usage_pct = recent[device_col].mean() * 100
        else:
            # Если колонки нет, пробуем с заглавной
            usage_pct = recent[device].mean() * 100 if device in recent.columns else 0
        device_usage[device] = usage_pct
    
    # 3. Тренд (растет или падает потребление)
    if len(recent) >= 24:
        recent_avg = recent['energy'].tail(24).mean()
        older_avg = recent['energy'].head(24).mean()
        trend_factor = max(0.5, min(1.5, recent_avg / older_avg if older_avg > 0 else 1))
    else:
        trend_factor = 1
    
    # 4. Расчет амортизации для каждого прибора
    amortization_results = {}
    for device, weight in DEVICE_WEIGHTS.items():
        usage = device_usage[device]
        
        # Базовая амортизация от частоты использования
        usage_score = (usage / 100) * 50
        
        # Корректировка от нагрузки (чем выше нагрузка, тем быстрее износ)
        load_score = energy_factor * 30
        
        # Долговременная составляющая (базовый износ)
        base_score = weight * 20
        
        # Итоговая амортизация
        score = usage_score + load_score + base_score
        score = score * trend_factor
        
        # Ограничиваем и округляем
        score = min(100, max(5, round(score, 1)))
        
        amortization_results[device] = {
            'score': score,
            'usage': round(usage, 1),
            'weight': round(weight * 100),
            'status': get_amortization_status(score)
        }
    
    # Общая амортизация (взвешенная сумма)
    overall = sum(amortization_results[d]['score'] * DEVICE_WEIGHTS[d] for d in DEVICE_WEIGHTS)
    overall = min(100, max(5, round(overall, 1)))
    
    return {
        'devices': amortization_results,
        'overall': overall,
        'status': get_amortization_status(overall),
        'avg_energy': round(avg_energy, 2),
        'peak_energy': round(max_energy, 2),
        'trend': round(trend_factor, 2)
    }

def get_amortization_status(score):
    if score < 25:
        return {'text': 'Отличное', 'color': '#4caf50', 'icon': '✅', 'class': 'excellent'}
    elif score < 45:
        return {'text': 'Хорошее', 'color': '#8bc34a', 'icon': '🟢', 'class': 'good'}
    elif score < 65:
        return {'text': 'Удовлетворительное', 'color': '#ffc107', 'icon': '⚠️', 'class': 'warning'}
    elif score < 85:
        return {'text': 'Требует внимания', 'color': '#ff9800', 'icon': '🔴', 'class': 'attention'}
    else:
        return {'text': 'Критическое', 'color': '#f44336', 'icon': '‼️', 'class': 'critical'}

def data_stream_loop():
    """Фоновый поток для передачи данных с периодическим обновлением амортизации."""
    global current_index, is_streaming, csv_data, historical_window, last_amortization_update, amortization_cache
    
    print("📡 Поток данных запущен")
    
    # Сразу заполняем историческое окно первыми 500 записями
    initial_count = min(500, len(csv_data))
    for i in range(initial_count):
        record = csv_data[i]
        historical_window.append({
            'timestamp': record.get('Unix Timestamp', 0),
            'energy': record.get('Energy Consumption (kWh)', 0),
            'voltage': record.get('Voltage', 0),
            'television': record.get('Television', 0),
            'dryer': record.get('Dryer', 0),
            'oven': record.get('Oven', 0),
            'refrigerator': record.get('Refrigerator', 0),
            'microwave': record.get('Microwave', 0)
        })
    
    # Первый расчет амортизации
    amortization_cache = calculate_stable_amortization()
    last_amortization_update = time.time()
    
    while is_streaming and current_index < len(csv_data):
        record = csv_data[current_index]
        
        # Добавляем запись в историческое окно
        current_record = {
            'timestamp': record.get('Unix Timestamp', 0),
            'energy': record.get('Energy Consumption (kWh)', 0),
            'voltage': record.get('Voltage', 0),
            'television': record.get('Television', 0),
            'dryer': record.get('Dryer', 0),
            'oven': record.get('Oven', 0),
            'refrigerator': record.get('Refrigerator', 0),
            'microwave': record.get('Microwave', 0)
        }
        historical_window.append(current_record)
        
        # Обновляем амортизацию раз в 30 секунд (а не для каждой записи)
        current_time = time.time()
        if current_time - last_amortization_update > 30 and len(historical_window) >= 100:
            amortization_cache = calculate_stable_amortization()
            last_amortization_update = current_time
        
        # Используем кешированную амортизацию
        amortization_to_send = amortization_cache if amortization_cache else {
            'devices': {}, 'overall': 0, 'status': {'text': 'Накопление данных...', 'color': '#999', 'icon': '⏳'},
            'avg_energy': 0, 'peak_energy': 0
        }
        
        # Отправляем данные клиенту
        data_to_emit = {
            'datetime': record.get('Datetime', ''),
            'datetime_short': record.get('Datetime', '')[5:16] if record.get('Datetime') else '',
            'energy': round(record.get('Energy Consumption (kWh)', 0), 2),
            'voltage': round(record.get('Voltage', 0), 1),
            'apparent_power': round(record.get('Apparent Power', 0), 1),
            'devices': {
                'television': record.get('Television', 0),
                'dryer': record.get('Dryer', 0),
                'oven': record.get('Oven', 0),
                'refrigerator': record.get('Refrigerator', 0),
                'microwave': record.get('Microwave', 0)
            },
            'amortization': amortization_to_send,
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
    global is_streaming, stream_thread, current_index
    if is_streaming:
        return
    if current_index >= len(csv_data):
        current_index = 0
    is_streaming = True
    stream_thread = threading.Thread(target=data_stream_loop)
    stream_thread.daemon = True
    stream_thread.start()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/status')
def get_status():
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
    if not csv_data:
        return jsonify([])
    return jsonify(csv_data[:100])

@app.route('/api/statistics')
def get_statistics():
    if not csv_data:
        return jsonify({'avg_energy': 0, 'max_energy': 0, 'min_energy': 0, 'avg_voltage': 230, 'total_records': 0})
    
    energies = [d.get('Energy Consumption (kWh)', 0) for d in csv_data]
    voltages = [d.get('Voltage', 0) for d in csv_data if d.get('Voltage', 0) > 0]
    
    return jsonify({
        'avg_energy': round(sum(energies) / len(energies), 2),
        'max_energy': round(max(energies), 2),
        'min_energy': round(min(energies), 2),
        'avg_voltage': round(sum(voltages) / len(voltages), 1) if voltages else 230,
        'total_records': len(csv_data)
    })

@socketio.on('connect')
def handle_connect():
    print("🔌 Клиент подключен")
    if csv_data and not is_streaming:
        start_data_stream()

@app.route('/analytics')
def analytics():
    """Страница аналитики и советов по экономии"""
    return render_template('analytics.html')
    
@app.route('/calculator')
def calculator():
    """Калькулятор сценариев Что, если?"""
    return render_template('calculator.html')

if __name__ == '__main__':
    print("="*50)
    print("СИСТЕМА КОНТРОЛЯ ЭНЕРГОПОТРЕБЛЕНИЯ")
    print("Умный дом с предиктивной амортизацией")
    print("="*50)
    
    if load_csv_data():
        print(f"\n Сервер запущен: http://localhost:5000")
        print(" Предиктивная амортизация рассчитывается раз в 30 секунд")
    else:
        print("\n Ошибка загрузки данных")
        exit(1)

    socketio.run(app, host='0.0.0.0', port=5000, debug=True)