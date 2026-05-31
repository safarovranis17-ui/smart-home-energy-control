import sqlite3
import pandas as pd
import os

def load_csv():
    csv_path = 'data/smart_home_dataset.csv'
    db_path = 'data/sensor_data.db'
    
    if not os.path.exists(csv_path):
        print(f"❌ Файл {csv_path} не найден!")
        print("   Сначала создайте CSV: python generate_realistic_data.py")
        return False
    
    print(f"📂 Чтение файла: {csv_path}")
    df = pd.read_csv(csv_path)
    print(f"   Найдено {len(df)} записей")
    
    # Подключаемся к БД
    conn = sqlite3.connect(db_path)
    
    # Удаляем старые таблицы
    conn.execute("DROP TABLE IF EXISTS sensor_readings")
    conn.execute("DROP TABLE IF EXISTS devices")
    
    # Создаем новую таблицу
    conn.execute('''
        CREATE TABLE sensor_readings (
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
    
    # Загружаем данные
    count = 0
    for _, row in df.iterrows():
        try:
            conn.execute('''
                INSERT INTO sensor_readings (
                    device_id, timestamp, datetime, television, dryer, oven,
                    refrigerator, microwave, line_voltage, voltage, apparent_power,
                    energy_consumption, hour, day_of_week, month, is_anomaly
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                'sensor_01',
                int(row['Unix Timestamp']),
                row['Datetime'],
                int(row['Television']),
                int(row['Dryer']),
                int(row['Oven']),
                int(row['Refrigerator']),
                int(row['Microwave']),
                float(row['Line Voltage']),
                float(row['Voltage']),
                float(row['Apparent Power']),
                float(row['Energy Consumption (kWh)']),
                int(row['Hour of the Day']),
                0,  # day_of_week
                1,  # month
                0   # is_anomaly
            ))
            count += 1
        except Exception as e:
            print(f"Ошибка: {e}")
    
    conn.commit()
    
    # Проверка
    cursor = conn.execute("SELECT COUNT(*) FROM sensor_readings")
    total = cursor.fetchone()[0]
    conn.close()
    
    print(f"✅ Загружено {total} записей в БД")
    return True

if __name__ == "__main__":
    load_csv()