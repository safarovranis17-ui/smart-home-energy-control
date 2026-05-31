import sqlite3
import pandas as pd
import os

print("="*60)
print("СОЗДАНИЕ БАЗЫ ДАННЫХ ИЗ CSV")
print("="*60)

csv_path = 'data/smart_home_dataset.csv'
db_path = 'data/sensor_data.db'

# Проверяем наличие CSV
if not os.path.exists(csv_path):
    print(f"❌ Файл {csv_path} не найден!")
    exit(1)

print(f"📂 Чтение CSV: {csv_path}")
df = pd.read_csv(csv_path)
print(f"   Найдено {len(df)} записей")
print(f"   Колонки: {df.columns.tolist()}")

# Удаляем старую БД
if os.path.exists(db_path):
    os.remove(db_path)
    print("   Старая БД удалена")

# Создаем новую БД
conn = sqlite3.connect(db_path)

# Создаем таблицу sensor_readings
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
print("✅ Таблица sensor_readings создана")

# Создаем таблицу devices
conn.execute('''
    CREATE TABLE devices (
        device_id TEXT PRIMARY KEY,
        device_name TEXT,
        location TEXT,
        device_type TEXT,
        last_seen INTEGER
    )
''')
print("✅ Таблица devices создана")

# Создаем таблицу events
conn.execute('''
    CREATE TABLE events (
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
print("✅ Таблица events создана")

# Регистрируем устройство
conn.execute('''
    INSERT INTO devices (device_id, device_name, location, device_type, last_seen)
    VALUES (?, ?, ?, ?, ?)
''', ('sensor_01', 'Датчик умного дома', 'Квартира', 'smart_meter', 0))
print("✅ Устройство зарегистрировано")

# Функция для преобразования названия дня в номер
def day_to_number(day_name):
    days = {'Monday': 0, 'Tuesday': 1, 'Wednesday': 2, 'Thursday': 3,
            'Friday': 4, 'Saturday': 5, 'Sunday': 6}
    return days.get(day_name, 0)

# Функция для преобразования названия месяца в номер
def month_to_number(month_name):
    months = {'January': 1, 'February': 2, 'March': 3, 'April': 4,
              'May': 5, 'June': 6, 'July': 7, 'August': 8,
              'September': 9, 'October': 10, 'November': 11, 'December': 12}
    return months.get(month_name, 1)

# Загружаем данные
print("\n📂 Загрузка данных в БД...")
count = 0
for index, row in df.iterrows():
    try:
        # Преобразуем день недели в число
        day_num = day_to_number(row['Day of the Week'])
        # Преобразуем месяц в число
        month_num = month_to_number(row['Month'])
        
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
            day_num,
            month_num,
            int(row.get('Is Anomaly', 0))
        ))
        count += 1
        
        if count % 1000 == 0:
            print(f"   Загружено {count} записей...")
            
    except Exception as e:
        print(f"   Ошибка в строке {index}: {e}")

conn.commit()

# Проверка
cursor = conn.execute("SELECT COUNT(*) FROM sensor_readings")
total = cursor.fetchone()[0]
conn.close()

print(f"\n✅ Загружено {total} записей в БД")
print("="*60)
print("Теперь запустите: python app.py")
print("="*60)