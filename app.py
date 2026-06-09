from flask import Flask, render_template, jsonify
from flask_cors import CORS
from flask_socketio import SocketIO, emit
import pandas as pd
import threading
import time
import os
from datetime import datetime

app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret!'
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*")

csv_data = []
current_index = 0
is_streaming = False
stream_thread = None

def load_csv_data():
    global csv_data
    print("="*50)
    print("📂 ПОИСК CSV-ФАЙЛА")
    print("="*50)
    
    possible_paths = [
        'data/smart_home_dataset.csv',
        './data/smart_home_dataset.csv',
        '../data/smart_home_dataset.csv',
        'smart_home_dataset.csv',
        './smart_home_dataset.csv'
    ]
    
    csv_path = None
    for path in possible_paths:
        if os.path.exists(path):
            csv_path = path
            print(f"✅ Файл найден: {path}")
            break
    
    if csv_path is None:
        print("❌ CSV-ФАЙЛ НЕ НАЙДЕН!")
        return False
    
    try:
        df = pd.read_csv(csv_path)
        csv_data = df.to_dict('records')
        print(f"✅ Загружено {len(csv_data)} записей")
        return True
    except Exception as e:
        print(f"❌ Ошибка чтения CSV: {e}")
        return False

def calculate_amortization_from_csv(recent_records):
    if len(recent_records) < 10:
        return None
    
    df = pd.DataFrame(recent_records)
    
    devices = ['Refrigerator', 'Oven', 'Microwave', 'Television', 'Dryer']
    devices_data = {}
    all_scores = []
    
    for device in devices:
        if device in df.columns:
            usage_count = (df[device] > 0).sum()
            usage_pct = round((usage_count / len(df)) * 100, 1)
            
            if device == 'Refrigerator':
                score = max(50, min(95, 95 - (usage_pct * 0.3)))
            elif device == 'Dryer':
                score = max(45, min(90, 90 - (usage_pct * 0.4)))
            elif device == 'Oven':
                score = max(50, min(92, 92 - (usage_pct * 0.35)))
            else:
                score = max(60, min(98, 98 - (usage_pct * 0.25)))
            
            score = round(score, 1)
            all_scores.append(score)
            
            devices_data[device] = {
                'score': score,
                'usage': usage_pct
            }
    
    if not all_scores:
        return None
    
    overall = round(sum(all_scores) / len(all_scores), 1)
    
    if overall >= 80:
        status_text = "Отличное"
        status_color = "#4caf50"
        status_icon = "✅"
    elif overall >= 60:
        status_text = "Хорошее"
        status_color = "#ff9800"
        status_icon = "⚠️"
    elif overall >= 40:
        status_text = "Требует внимания"
        status_color = "#ffc107"
        status_icon = "⚡"
    else:
        status_text = "Критическое"
        status_color = "#f44336"
        status_icon = "🔴"
    
    return {
        'overall': overall,
        'devices': devices_data,
        'status': {
            'text': status_text,
            'color': status_color,
            'icon': status_icon
        }
    }

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/analytics')
def analytics():
    return render_template('analytics.html')

@app.route('/calculator')
def calculator():
    return render_template('calculator.html')

@app.route('/api/status')
def get_status():
    total = len(csv_data)
    progress = round((current_index / total * 100), 1) if total > 0 else 0
    return jsonify({
        'is_streaming': is_streaming,
        'progress': progress,
        'current': current_index,
        'total': total
    })

@app.route('/api/data')
def get_initial_data():
    if not csv_data:
        return jsonify([])
    return jsonify(csv_data[:500])

@app.route('/api/statistics')
def get_statistics():
    if not csv_data:
        return jsonify({'avg_energy': 0, 'max_energy': 0, 'min_energy': 0, 'avg_voltage': 230, 'total_records': 0})
    
    energies = []
    for d in csv_data:
        e = d.get('Energy Consumption (kWh)', 0)
        if isinstance(e, str):
            try:
                e = float(e)
            except:
                e = 0
        energies.append(e)
    
    voltages = []
    for d in csv_data:
        v = d.get('Voltage', 0)
        if isinstance(v, str):
            try:
                v = float(v)
            except:
                v = 0
        if v > 0:
            voltages.append(v)
    
    return jsonify({
        'avg_energy': round(sum(energies) / len(energies), 2),
        'max_energy': round(max(energies), 2),
        'min_energy': round(min(energies), 2),
        'avg_voltage': round(sum(voltages) / len(voltages), 1) if voltages else 230,
        'total_records': len(csv_data)
    })

@app.route('/api/devices')
def api_devices():
    if not csv_data or len(csv_data) < 10:
        return jsonify({'devices': {}, 'overall': 0, 'status': {'text': 'Недостаточно данных', 'color': '#999', 'icon': '⏳'}})
    
    recent = csv_data[-100:]
    amortization = calculate_amortization_from_csv(recent)
    
    if amortization:
        return jsonify({
            'devices': amortization['devices'],
            'overall': amortization['overall'],
            'status': amortization['status'],
            'timestamp': datetime.now().isoformat()
        })
    else:
        return jsonify({'devices': {}, 'overall': 0, 'status': {'text': 'Накопление данных...', 'color': '#999', 'icon': '⏳'}})

@socketio.on('connect')
def handle_connect():
    print("🔌 Клиент подключен")

@socketio.on('request_single')
def handle_request_single():
    global current_index
    
    if not csv_data:
        emit('error', {'message': 'Нет данных'})
        return
    
    if current_index >= len(csv_data):
        emit('stream_finished', {'message': 'Все данные загружены'})
        return
    
    record = csv_data[current_index]
    
    devices_status = {
        'television': 1 if record.get('Television', 0) > 0 else 0,
        'dryer': 1 if record.get('Dryer', 0) > 0 else 0,
        'oven': 1 if record.get('Oven', 0) > 0 else 0,
        'refrigerator': 1 if record.get('Refrigerator', 0) > 0 else 0,
        'microwave': 1 if record.get('Microwave', 0) > 0 else 0
    }
    
    start_idx = max(0, current_index - 100)
    recent = csv_data[start_idx:current_index + 1]
    amortization = calculate_amortization_from_csv(recent)
    
    if amortization is None:
        amortization = {
            'overall': 50,
            'devices': {},
            'status': {'text': 'Накопление данных...', 'color': '#999', 'icon': '⏳'}
        }
    
    data_to_emit = {
        'datetime': record.get('Datetime', ''),
        'datetime_short': record.get('Datetime', '')[-8:] if record.get('Datetime') else '',
        'energy': round(record.get('Energy Consumption (kWh)', 0), 2),
        'voltage': round(record.get('Voltage', 0), 1),
        'devices': devices_status,
        'amortization': amortization,
        'progress': round((current_index + 1) / len(csv_data) * 100, 1),
        'current': current_index + 1,
        'total': len(csv_data)
    }
    
    socketio.emit('new_data', data_to_emit)
    current_index += 1

@socketio.on('reset_stream')
def reset_stream():
    global current_index
    current_index = 0
    emit('stream_reset', {'message': 'Stream reset'})

if __name__ == '__main__':
    print("="*50)
    print("🚀 ЗАПУСК СЕРВЕРА")
    print("="*50)
    
    if load_csv_data():
        print(f"\n🌐 СЕРВЕР ЗАПУЩЕН")
        print("   http://localhost:5000")
        print("="*50)
    else:
        print("\n❌ НЕ УДАЛОСЬ ЗАГРУЗИТЬ CSV")
        exit(1)
    
    socketio.run(app, host='0.0.0.0', port=5000, debug=True, use_reloader=False)