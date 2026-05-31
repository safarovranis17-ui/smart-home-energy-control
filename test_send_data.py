"""
Скрипт для тестирования отправки данных на сервер
Имитирует работу реального датчика
"""

import requests
import time
import random
from datetime import datetime

API_URL = "http://localhost:5000/api/data"

def generate_test_reading():
    """Генерирует тестовое показание"""
    hour = datetime.now().hour
    
    # Базовые вероятности в зависимости от времени суток
    if 7 <= hour <= 9:  # Утро
        oven_prob = 0.3
        tv_prob = 0.2
    elif 12 <= hour <= 14:  # Обед
        oven_prob = 0.4
        tv_prob = 0.1
    elif 18 <= hour <= 22:  # Вечер
        oven_prob = 0.5
        tv_prob = 0.7
    else:  # Ночь
        oven_prob = 0.05
        tv_prob = 0.1
    
    reading = {
        "device_id": "sensor_01",
        "timestamp": int(time.time()),
        "television": 1 if random.random() < tv_prob else 0,
        "dryer": 1 if random.random() < 0.1 else 0,
        "oven": 1 if random.random() < oven_prob else 0,
        "refrigerator": 1,
        "microwave": 1 if random.random() < 0.15 else 0,
        "energy_consumption": round(random.uniform(0.5, 5.0), 2),
        "line_voltage": round(random.uniform(220, 240), 1),
        "current": round(random.uniform(2, 20), 1),
        "temperature": round(random.uniform(20, 25), 1),
        "humidity": round(random.uniform(40, 60), 1)
    }
    
    return reading

def send_readings():
    """Отправляет показания на сервер"""
    print("Начинаем отправку тестовых данных...")
    print("Нажмите Ctrl+C для остановки\n")
    
    count = 0
    try:
        while True:
            reading = generate_test_reading()
            
            response = requests.post(API_URL, json=reading)
            
            if response.status_code == 201:
                count += 1
                data = response.json()
                print(f"[{count}] ✓ Данные отправлены | Энергия: {reading['energy_consumption']} кВт·ч | Аномалия: {data.get('is_anomaly', False)}")
            else:
                print(f"[{count}] ✗ Ошибка: {response.text}")
            
            time.sleep(10)  # Отправка каждые 10 секунд
            
    except KeyboardInterrupt:
        print(f"\n\nОтправлено {count} показаний")

if __name__ == "__main__":
    send_readings()