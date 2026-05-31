import pandas as pd
import numpy as np
from datetime import datetime
import os

def load_data(filepath):
    """Загружает данные из CSV файла"""
    print(f"Загрузка данных из {filepath}...")
    df = pd.read_csv(filepath)
    
    # Преобразуем Unix Timestamp в datetime
    df['Datetime'] = pd.to_datetime(df['Unix Timestamp'], unit='s')
    
    # Сортируем по времени
    df = df.sort_values('Datetime')
    
    print(f"Загружено {len(df)} записей")
    print(f"Период: с {df['Datetime'].min()} по {df['Datetime'].max()}")
    
    return df

def preprocess_data(df):
    """Предобработка данных и создание признаков для ML"""
    df_processed = df.copy()
    
    # Определяем названия колонок
    energy_col = 'Energy Consumption (kWh)' if 'Energy Consumption (kWh)' in df.columns else 'energy_consumption'
    
    # Обработка datetime - универсальный способ
    if 'datetime' in df.columns:
        # Пробуем разные форматы
        try:
            df_processed['datetime'] = pd.to_datetime(df_processed['datetime'], format='%Y-%m-%d %H:%M:%S')
        except:
            try:
                df_processed['datetime'] = pd.to_datetime(df_processed['datetime'], format='%Y-%m-%dT%H:%M:%S')
            except:
                df_processed['datetime'] = pd.to_datetime(df_processed['datetime'], format='mixed')
        
        df_processed['Hour'] = df_processed['datetime'].dt.hour
        df_processed['DayOfWeek'] = df_processed['datetime'].dt.dayofweek
        df_processed['Month'] = df_processed['datetime'].dt.month
    elif 'Datetime' in df.columns:
        try:
            df_processed['Datetime'] = pd.to_datetime(df_processed['Datetime'], format='%Y-%m-%d %H:%M:%S')
        except:
            try:
                df_processed['Datetime'] = pd.to_datetime(df_processed['Datetime'], format='%Y-%m-%dT%H:%M:%S')
            except:
                df_processed['Datetime'] = pd.to_datetime(df_processed['Datetime'], format='mixed')
        
        df_processed['Hour'] = df_processed['Datetime'].dt.hour
        df_processed['DayOfWeek'] = df_processed['Datetime'].dt.dayofweek
        df_processed['Month'] = df_processed['Datetime'].dt.month
    elif 'hour' in df.columns:
        df_processed['Hour'] = df_processed['hour']
        df_processed['DayOfWeek'] = df_processed.get('day_of_week', 0)
        df_processed['Month'] = df_processed.get('month', 1)
    else:
        df_processed['Hour'] = 12
        df_processed['DayOfWeek'] = 0
        df_processed['Month'] = 1
    
    # Скользящие средние
    df_processed['Energy_MA_6'] = df_processed[energy_col].rolling(window=6, min_periods=1).mean()
    df_processed['Energy_MA_12'] = df_processed[energy_col].rolling(window=12, min_periods=1).mean()
    df_processed['Energy_MA_24'] = df_processed[energy_col].rolling(window=24, min_periods=1).mean()
    
    # Количество активных приборов
    device_cols = ['Television', 'Dryer', 'Oven', 'Refrigerator', 'Microwave']
    device_cols_lower = ['television', 'dryer', 'oven', 'refrigerator', 'microwave']
    
    existing_cols = [c for c in device_cols + device_cols_lower if c in df.columns]
    if existing_cols:
        df_processed['Total_Appliances_On'] = df_processed[existing_cols].sum(axis=1)
        df_processed['Active_Devices_Count'] = df_processed[existing_cols].sum(axis=1)
    else:
        df_processed['Total_Appliances_On'] = 0
        df_processed['Active_Devices_Count'] = 0
    
    # Добавляем колонки приборов для модели
    for device in device_cols:
        device_lower = device.lower()
        if device_lower in df.columns:
            df_processed[device] = df_processed[device_lower]
        elif device not in df.columns:
            df_processed[device] = 0
    
    # Лаговые признаки
    for lag in [1, 2, 3, 6, 12, 24]:
        df_processed[f'Energy_Lag_{lag}'] = df_processed[energy_col].shift(lag)
    
    # Заполняем NaN нулями
    df_processed = df_processed.fillna(0)
    
    return df_processed

def get_device_usage_stats(df):
    """Статистика использования приборов"""
    appliances = ['Television', 'Dryer', 'Oven', 'Refrigerator', 'Microwave']
    
    stats = {}
    for appliance in appliances:
        appliance_lower = appliance.lower()
        # Проверяем оба варианта названия
        if appliance in df.columns:
            col = appliance
        elif appliance_lower in df.columns:
            col = appliance_lower
        else:
            stats[appliance] = {
                'total_hours': 0,
                'active_percentage': 0,
                'avg_energy_when_on': 0
            }
            continue
        
        stats[appliance] = {
            'total_hours': float(df[col].sum()),
            'active_percentage': float((df[col].sum() / len(df)) * 100) if len(df) > 0 else 0,
            'avg_energy_when_on': float(df[df[col] == 1]['energy_consumption'].mean()) if len(df[df[col] == 1]) > 0 else 0
        }
    
    return stats

def get_hourly_energy_profile(df):
    """Часовой профиль энергопотребления"""
    # Определяем колонку с часом
    if 'hour' in df.columns:
        hour_col = 'hour'
    elif 'Hour' in df.columns:
        hour_col = 'Hour'
    elif 'Hour of the Day' in df.columns:
        hour_col = 'Hour of the Day'
    else:
        # Создаем заглушку
        df = df.copy()
        df['Hour'] = 12
        hour_col = 'Hour'
    
    # Определяем колонку с энергией
    if 'energy_consumption' in df.columns:
        energy_col = 'energy_consumption'
    elif 'Energy Consumption (kWh)' in df.columns:
        energy_col = 'Energy Consumption (kWh)'
    else:
        energy_col = None
    
    if energy_col:
        hourly = df.groupby(hour_col)[energy_col].agg(['mean', 'std', 'max', 'min']).reset_index()
        hourly.rename(columns={hour_col: 'Hour'}, inplace=True)
    else:
        hourly = pd.DataFrame({'Hour': range(24), 'mean': 0, 'std': 0, 'max': 0, 'min': 0})
    
    return hourly

def get_daily_energy_profile(df):
    """Дневной профиль энергопотребления"""
    df['Date'] = df['Datetime'].dt.date
    daily = df.groupby('Date')['Energy Consumption (kWh)'].sum().reset_index()
    return daily