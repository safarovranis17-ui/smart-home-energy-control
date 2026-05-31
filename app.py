from flask import Flask, render_template, jsonify, request
from flask_cors import CORS
from flask_socketio import SocketIO, emit
import pandas as pd
import numpy as np
from datetime import datetime
import os
import sqlite3
import math
import time
import threading

from database import SensorDatabase
from data_processor import DataProcessor
from data_loader import load_data, preprocess_data
from model import EnergyPredictor
from utils import calculate_predictive_amortization, generate_alerts

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-here'
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*")

database = None
predictor = None
data_processor = DataProcessor()

auto_play_enabled = False
auto_play_thread = None
auto_play_index = 0
auto_play_data = []
auto_play_speed = 1.0

def clean_for_json(obj):
    if isinstance(obj, dict):
        return {key: clean_for_json(value) for key, value in obj.items()}
    elif isinstance(obj, list):
        return [clean_for_json(item) for item in obj]
    elif isinstance(obj, float):
        if math.isnan(obj) or math.isinf(obj):
            return 0
        return obj
    elif isinstance(obj, (np.float64, np.float32)):
        if np.isnan(obj) or np.isinf(obj):
            return 0.0
        return float(obj)
    elif isinstance(obj, (np.int64, np.int32)):
        return int(obj)
    elif pd.isna(obj):
        return 0
    else:
        return obj

def load_data_to_memory():
    try:
        conn = sqlite3.connect('data/sensor_data.db')
        df = pd.read_sql_query("""
            SELECT id, timestamp, datetime, device_id, 
                   television, dryer, oven, refrigerator, microwave,
                   line_voltage, voltage, apparent_power, energy_consumption,
                   hour, day_of_week, month, is_anomaly
            FROM sensor_readings 
            ORDER BY timestamp ASC
        """, conn)
        conn.close()
        data = df.to_dict('records')
        print(f"   Загружено {len(data)} записей для автовоспроизведения")
        return data
    except Exception as e:
        print(f"   Ошибка загрузки данных: {e}")
        return []

def auto_play_loop():
    global auto_play_enabled, auto_play_index, auto_play_data, auto_play_speed
    
    print("🔄 Поток автовоспроизведения запущен")
    
    while auto_play_enabled and auto_play_index < len(auto_play_data):
        record = auto_play_data[auto_play_index]
        
        try:
            socketio.emit('sensor_data', {
                'datetime': record['datetime'],
                'energy_consumption': record['energy_consumption'],
                'television': record['television'],
                'dryer': record['dryer'],
                'oven': record['oven'],
                'refrigerator': record['refrigerator'],
                'microwave': record['microwave'],
                'is_anomaly': record.get('is_anomaly', 0),
                'progress': (auto_play_index / len(auto_play_data)) * 100
            })
            
            auto_play_index += 1
            
            if auto_play_index < len(auto_play_data):
                prev_time = auto_play_data[auto_play_index - 1]['timestamp']
                next_time = auto_play_data[auto_play_index]['timestamp']
                delay = (next_time - prev_time) / auto_play_speed
                if delay > 0 and delay < 60:
                    time.sleep(delay)
                elif delay >= 60:
                    time.sleep(1)
                    
        except Exception as e:
            print(f"Ошибка при воспроизведении: {e}")
            auto_play_index += 1
            time.sleep(0.1)
    
    auto_play_enabled = False
    print("✅ Воспроизведение завершено")

def start_auto_play(speed=1.0):
    global auto_play_enabled, auto_play_index, auto_play_speed, auto_play_thread
    
    if auto_play_enabled:
        return False
    
    if len(auto_play_data) == 0:
        data = load_data_to_memory()
        if len(data) == 0:
            return False
    
    auto_play_enabled = True
    auto_play_speed = speed
    
    if auto_play_index >= len(auto_play_data):
        auto_play_index = 0
    
    auto_play_thread = threading.Thread(target=auto_play_loop, daemon=True)
    auto_play_thread.start()
    return True

def stop_auto_play():
    global auto_play_enabled
    auto_play_enabled = False
    return True

def reset_auto_play():
    global auto_play_index
    auto_play_index = 0
    return True

def initialize_system():
    global database, predictor, auto_play_data
    
    print("\n" + "="*60)
    print("ЗАПУСК СИСТЕМЫ УМНОГО ДОМА")
    print("="*60)
    
    print("\n1. Подключение к базе данных...")
    database = SensorDatabase()
    
    print("\n2. Загрузка данных в память...")
    auto_play_data = load_data_to_memory()
    
    total_readings = len(auto_play_data)
    print(f"\n📊 В базе данных {total_readings} записей")
    
    print("\n3. Инициализация ML модели...")
    predictor = EnergyPredictor()
    
    if predictor.load_model():
        print("   ✅ Модель загружена")
    else:
        print("   ⚠️ Модель не найдена")
    
    print("\n" + "="*60)
    print("СЕРВЕР ЗАПУЩЕН")
    print("GET    /             - веб-интерфейс")
    print("POST   /api/play/start  - запуск воспроизведения")
    print("POST   /api/play/stop   - остановка")
    print("="*60)
    
    return True

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/status', methods=['GET'])
def system_status():
    return jsonify({
        'status': 'running',
        'total_readings': len(auto_play_data),
        'auto_play_enabled': auto_play_enabled,
        'auto_play_progress': (auto_play_index / len(auto_play_data) * 100) if len(auto_play_data) > 0 else 0
    })

@app.route('/api/statistics', methods=['GET'])
def get_statistics():
    if len(auto_play_data) == 0:
        return jsonify({'avg_energy': 0, 'max_energy': 0, 'min_energy': 0, 'total_readings': 0})
    
    df = pd.DataFrame(auto_play_data)
    stats = {
        'avg_energy': round(df['energy_consumption'].mean(), 2),
        'max_energy': round(df['energy_consumption'].max(), 2),
        'min_energy': round(df['energy_consumption'].min(), 2),
        'total_readings': len(df),
        'anomaly_count': int(df['is_anomaly'].sum()) if 'is_anomaly' in df.columns else 0,
        'avg_voltage': 230
    }
    return jsonify(stats)

@app.route('/api/data', methods=['GET'])
def get_data():
    limit = request.args.get('limit', 100, type=int)
    if len(auto_play_data) > limit:
        data = auto_play_data[-limit:]
    else:
        data = auto_play_data
    return jsonify(clean_for_json(data))

@app.route('/api/events', methods=['GET'])
def get_events():
    return jsonify([])

@app.route('/api/amortization', methods=['GET'])
def get_amortization():
    if len(auto_play_data) < 10:
        return jsonify({'error': 'Недостаточно данных'}), 400
    
    df = pd.DataFrame(auto_play_data)
    avg_energy = df['energy_consumption'].mean()
    max_energy = df['energy_consumption'].max()
    
    device_names = ['Television', 'Dryer', 'Oven', 'Refrigerator', 'Microwave']
    device_keys = ['television', 'dryer', 'oven', 'refrigerator', 'microwave']
    
    result = {}
    for name, key in zip(device_names, device_keys):
        if key in df.columns:
            usage = df[key].mean() * 100
            score = min(100, usage * 0.7 + (avg_energy / max_energy) * 30)
            result[name] = {
                'amortization_score': round(score, 1),
                'usage_frequency': round(usage, 1),
                'status': {'text': 'Хорошее' if score < 40 else 'Требует внимания' if score < 70 else 'Критическое'}
            }
    
    total_score = sum([result[d]['amortization_score'] for d in device_names if d in result]) / len(device_names)
    result['total'] = {
        'amortization_score': round(total_score, 1),
        'predicted_avg_load': round(avg_energy, 2),
        'peak_load': round(max_energy, 2),
        'status': {'text': 'Хорошее' if total_score < 40 else 'Требует внимания' if total_score < 70 else 'Критическое'}
    }
    
    return jsonify(result)

@app.route('/api/forecast', methods=['GET'])
def get_forecast():
    hours_ahead = request.args.get('hours', 24, type=int)
    if len(auto_play_data) < 24:
        predictions = [2.5] * hours_ahead
    else:
        df = pd.DataFrame(auto_play_data[-168:])
        avg_by_hour = df.groupby('hour')['energy_consumption'].mean().to_dict()
        predictions = []
        for h in range(hours_ahead):
            hour = (datetime.now().hour + h) % 24
            predictions.append(round(avg_by_hour.get(hour, 2.5), 2))
    
    return jsonify({'predictions': predictions, 'hours': list(range(1, hours_ahead + 1))})

@app.route('/api/play/start', methods=['POST'])
def start_playback():
    data = request.get_json() or {}
    speed = data.get('speed', 1.0)
    if start_auto_play(speed=speed):
        return jsonify({'status': 'started', 'total_records': len(auto_play_data), 'speed': speed})
    return jsonify({'status': 'error', 'message': 'Не удалось запустить'}), 400

@app.route('/api/play/stop', methods=['POST'])
def stop_playback():
    stop_auto_play()
    return jsonify({'status': 'stopped'})

@app.route('/api/play/reset', methods=['POST'])
def reset_playback():
    reset_auto_play()
    return jsonify({'status': 'reset'})

@app.route('/api/play/status', methods=['GET'])
def playback_status():
    total = len(auto_play_data)
    progress = (auto_play_index / total * 100) if total > 0 else 0
    return jsonify({
        'is_playing': auto_play_enabled,
        'progress': round(progress, 1),
        'current_index': auto_play_index,
        'total_records': total,
        'speed': auto_play_speed
    })

@app.route('/api/play/speed', methods=['POST'])
def set_playback_speed():
    global auto_play_speed
    data = request.get_json()
    auto_play_speed = data.get('speed', 1.0)
    return jsonify({'status': 'ok', 'speed': auto_play_speed})

@app.route('/favicon.ico')
def favicon():
    return '', 204

@socketio.on('connect')
def handle_connect():
    print("🔌 Клиент подключен")
    emit('connected', {'message': 'Connected'})

if __name__ == '__main__':
    initialize_system()
    
    print("\n" + "="*60)
    print("🌐 ЗАПУСК WEB-СЕРВЕРА")
    print("📱 Откройте в браузере: http://localhost:5000")
    print("🎮 Для запуска воспроизведения: POST /api/play/start")
    print("="*60 + "\n")
    
    socketio.run(app, host='0.0.0.0', port=5000, debug=True)