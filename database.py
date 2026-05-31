import sqlite3
import pandas as pd
from datetime import datetime
import os

class SensorDatabase:
    
    def __init__(self, db_path='data/sensor_data.db'):
        self.db_path = db_path
        os.makedirs('data', exist_ok=True)
        self.init_database()
    
    def init_database(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Таблица sensor_readings - БЕЗ ПОЛЯ current
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS sensor_readings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                device_id TEXT,
                timestamp INTEGER,
                datetime TEXT,
                television INTEGER,
                dryer INTEGER,
                oven INTEGER,
                refrigerator INTEGER,
                microwave INTEGER,
                line_voltage REAL,
                voltage REAL,
                apparent_power REAL,
                energy_consumption REAL,
                hour INTEGER,
                day_of_week INTEGER,
                month INTEGER,
                is_anomaly INTEGER
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS devices (
                device_id TEXT PRIMARY KEY,
                device_name TEXT,
                location TEXT,
                device_type TEXT,
                last_seen INTEGER
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp INTEGER,
                device_id TEXT,
                event_type TEXT,
                severity TEXT,
                message TEXT,
                is_resolved INTEGER DEFAULT 0,
                resolved_at INTEGER
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS predictions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp INTEGER,
                prediction_hour INTEGER,
                predicted_energy REAL,
                actual_energy REAL,
                model_version TEXT
            )
        ''')
        
        conn.commit()
        conn.close()
        print("✅ База данных инициализирована")
    
    def save_reading(self, reading):
        """Сохраняет показание - БЕЗ ПОЛЯ current"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Убираем поле current если оно есть
        if 'current' in reading:
            del reading['current']
        
        columns = ', '.join(reading.keys())
        placeholders = ', '.join(['?' for _ in reading])
        query = f"INSERT OR REPLACE INTO sensor_readings ({columns}) VALUES ({placeholders})"
        
        try:
            cursor.execute(query, list(reading.values()))
            conn.commit()
        except Exception as e:
            print(f"Ошибка сохранения в БД: {e}")
        finally:
            conn.close()
    
    def save_readings_batch(self, readings):
        """Сохраняет пакет показаний"""
        conn = sqlite3.connect(self.db_path)
        
        for reading in readings:
            if 'current' in reading:
                del reading['current']
        
        try:
            df = pd.DataFrame(readings)
            df.to_sql('sensor_readings', conn, if_exists='append', index=False)
        except Exception as e:
            print(f"Ошибка пакетного сохранения: {e}")
        finally:
            conn.close()
    
    def get_readings(self, start_time=None, end_time=None, limit=1000, device_id=None):
        conn = sqlite3.connect(self.db_path)
        
        query = "SELECT * FROM sensor_readings"
        conditions = []
        params = []
        
        if device_id:
            conditions.append("device_id = ?")
            params.append(device_id)
        if start_time:
            conditions.append("timestamp >= ?")
            params.append(start_time)
        if end_time:
            conditions.append("timestamp <= ?")
            params.append(end_time)
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        query += " ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)
        
        df = pd.read_sql_query(query, conn, params=params)
        conn.close()
        return df
    
    def get_latest_reading(self, device_id='sensor_01'):
        conn = sqlite3.connect(self.db_path)
        df = pd.read_sql_query(
            "SELECT * FROM sensor_readings WHERE device_id = ? ORDER BY timestamp DESC LIMIT 1",
            conn,
            params=(device_id,)
        )
        conn.close()
        if len(df) > 0:
            return df.iloc[0].to_dict()
        return None
    
    def get_statistics(self, hours=24):
        conn = sqlite3.connect(self.db_path)
        cutoff_time = int(datetime.now().timestamp()) - hours * 3600
        
        df = pd.read_sql_query("""
            SELECT 
                AVG(energy_consumption) as avg_energy,
                MAX(energy_consumption) as max_energy,
                MIN(energy_consumption) as min_energy,
                SUM(CASE WHEN is_anomaly = 1 THEN 1 ELSE 0 END) as anomaly_count,
                COUNT(*) as total_readings,
                AVG(line_voltage) as avg_voltage
            FROM sensor_readings 
            WHERE timestamp >= ?
        """, conn, params=(cutoff_time,))
        
        conn.close()
        if len(df) > 0:
            return df.iloc[0].to_dict()
        return {}
    
    def register_device(self, device_id, device_name, location, device_type):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT OR REPLACE INTO devices (device_id, device_name, location, device_type, last_seen)
            VALUES (?, ?, ?, ?, ?)
        ''', (device_id, device_name, location, device_type, int(datetime.now().timestamp())))
        conn.commit()
        conn.close()
    
    def save_event(self, device_id, event_type, severity, message):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO events (timestamp, device_id, event_type, severity, message)
            VALUES (?, ?, ?, ?, ?)
        ''', (int(datetime.now().timestamp()), device_id, event_type, severity, message))
        conn.commit()
        conn.close()
    
    def get_unresolved_events(self):
        conn = sqlite3.connect(self.db_path)
        df = pd.read_sql_query(
            "SELECT * FROM events WHERE is_resolved = 0 ORDER BY timestamp DESC",
            conn
        )
        conn.close()
        return df
    
    def save_prediction(self, timestamp, prediction_hour, predicted_energy, model_version='v1'):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO predictions (timestamp, prediction_hour, predicted_energy, model_version)
            VALUES (?, ?, ?, ?)
        ''', (timestamp, prediction_hour, predicted_energy, model_version))
        conn.commit()
        conn.close()