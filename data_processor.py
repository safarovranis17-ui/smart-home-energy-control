import pandas as pd
import numpy as np
from datetime import datetime

class DataProcessor:
    """Обработка сырых данных с датчиков"""
    
    @staticmethod
    def validate_reading(reading):
        """Валидация показаний датчика"""
        required_fields = ['device_id', 'timestamp', 'energy_consumption']
        
        for field in required_fields:
            if field not in reading:
                return False, f"Отсутствует поле: {field}"
        
        # Проверка значений
        if reading['energy_consumption'] < 0 or reading['energy_consumption'] > 20:
            return False, "Некорректное значение энергопотребления"
        
        if 'line_voltage' in reading and (reading['line_voltage'] < 180 or reading['line_voltage'] > 260):
            return False, "Некорректное напряжение"
        
        return True, "OK"
    
    @staticmethod
    def process_reading(raw_reading):
        """Обрабатывает сырые данные, добавляет вычисляемые поля"""
        dt = datetime.fromtimestamp(raw_reading['timestamp'])
        
        processed = {
            'device_id': raw_reading.get('device_id', 'sensor_01'),
            'timestamp': raw_reading['timestamp'],
            'datetime': dt.isoformat(),
            
            # Состояния приборов
            'television': int(raw_reading.get('television', 0)),
            'dryer': int(raw_reading.get('dryer', 0)),
            'oven': int(raw_reading.get('oven', 0)),
            'refrigerator': int(raw_reading.get('refrigerator', 1)),  # По умолчанию включен
            'microwave': int(raw_reading.get('microwave', 0)),
            
            # Электрические параметры
            'line_voltage': float(raw_reading.get('line_voltage', 230.0)),
            'voltage': float(raw_reading.get('voltage', 225.0)),
            'current': float(raw_reading.get('current', 0)),
            'apparent_power': float(raw_reading.get('apparent_power', 0)),
            'active_power': float(raw_reading.get('active_power', 0)),
            'power_factor': float(raw_reading.get('power_factor', 0.95)),
            'energy_consumption': float(raw_reading['energy_consumption']),
            
            # Дополнительные параметры
            'temperature': float(raw_reading.get('temperature', 22.0)),
            'humidity': float(raw_reading.get('humidity', 50.0)),
            'is_anomaly': int(raw_reading.get('is_anomaly', 0)),
            
            # Временные признаки
            'hour': dt.hour,
            'day_of_week': dt.weekday(),
            'month': dt.month
        }
        
        # Вычисляем apparent power если не указано
        if processed['apparent_power'] == 0 and processed['current'] > 0:
            processed['apparent_power'] = processed['current'] * processed['line_voltage']
        
        # Вычисляем active power если не указано
        if processed['active_power'] == 0:
            processed['active_power'] = processed['energy_consumption'] * 1000  # kWh to W
        
        # Обнаружение аномалий
        if not processed['is_anomaly']:
            processed['is_anomaly'] = DataProcessor.detect_anomaly(processed)
        
        return processed
    
    @staticmethod
    def detect_anomaly(reading):
        """Обнаружение аномалий в показаниях"""
        # Энергопотребление слишком высокое
        if reading['energy_consumption'] > 10:
            return 1
        
        # Напряжение вне нормы
        if reading['line_voltage'] < 200 or reading['line_voltage'] > 250:
            return 1
        
        # Несколько приборов одновременно (признак перегрузки)
        active_devices = sum([
            reading['television'], reading['dryer'], 
            reading['oven'], reading['microwave']
        ])
        if active_devices >= 3 and reading['energy_consumption'] > 8:
            return 1
        
        return 0
    
    @staticmethod
    def aggregate_readings(readings, interval_minutes=15):
        """Агрегирует показания за интервал"""
        df = pd.DataFrame(readings)
        
        if len(df) == 0:
            return []
        
        df['datetime'] = pd.to_datetime(df['datetime'])
        df.set_index('datetime', inplace=True)
        
        # Ресемплинг
        aggregated = df.resample(f'{interval_minutes}T').agg({
            'energy_consumption': 'mean',
            'line_voltage': 'mean',
            'television': 'max',
            'dryer': 'max',
            'oven': 'max',
            'refrigerator': 'max',
            'microwave': 'max',
            'temperature': 'mean',
            'humidity': 'mean'
        }).dropna()
        
        aggregated = aggregated.reset_index()
        return aggregated.to_dict('records')