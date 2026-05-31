import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.preprocessing import StandardScaler
import joblib
import warnings
warnings.filterwarnings('ignore')

class EnergyPredictor:
    def __init__(self):
        self.model = None
        self.scaler = StandardScaler()
        self.feature_columns = None
        self.is_trained = False
        
    def prepare_features(self, df):
        """Подготовка признаков для обучения"""
        # Определяем колонку с энергией
        if 'energy_consumption' in df.columns:
            energy_col = 'energy_consumption'
        elif 'Energy Consumption (kWh)' in df.columns:
            energy_col = 'Energy Consumption (kWh)'
        else:
            energy_col = None
        
        if energy_col is None:
            print("❌ Не найден столбец с энергопотреблением")
            return None, None
        
        # Создаем копию для работы
        data = df.copy()
        
        # Простые и надежные признаки
        feature_cols = []
        
        # Временные признаки
        if 'Hour' in data.columns:
            feature_cols.append('Hour')
        elif 'hour' in data.columns:
            data['Hour'] = data['hour']
            feature_cols.append('Hour')
        else:
            data['Hour'] = 12
            feature_cols.append('Hour')
        
        if 'DayOfWeek' in data.columns:
            feature_cols.append('DayOfWeek')
        elif 'day_of_week' in data.columns:
            data['DayOfWeek'] = data['day_of_week']
            feature_cols.append('DayOfWeek')
        else:
            data['DayOfWeek'] = 3
            feature_cols.append('DayOfWeek')
        
        # Признаки приборов (используем только существующие)
        device_cols = ['Television', 'Dryer', 'Oven', 'Refrigerator', 'Microwave']
        device_lower = ['television', 'dryer', 'oven', 'refrigerator', 'microwave']
        
        for i, dev in enumerate(device_lower):
            if dev in data.columns:
                data[device_cols[i]] = data[dev]
                feature_cols.append(device_cols[i])
            elif device_cols[i] in data.columns:
                feature_cols.append(device_cols[i])
        
        # Если нет данных о приборах, создаем заглушки
        added_devices = 0
        for dev in device_cols:
            if dev not in feature_cols:
                data[dev] = 0
                feature_cols.append(dev)
                added_devices += 1
        
        # Количество активных приборов (НО НЕ ДОБАВЛЯЕМ КАК ПРИЗНАК ДЛЯ ПРОГНОЗА)
        # Просто для информации
        active_cols = [c for c in device_cols if c in data.columns]
        if active_cols:
            data['Active_Devices_Count'] = data[active_cols].sum(axis=1)
        
        # Лаговые признаки (только для обучения, не для прогноза)
        data['Energy_Lag_1'] = data[energy_col].shift(1).fillna(0)
        data['Energy_Lag_2'] = data[energy_col].shift(2).fillna(0)
        data['Energy_Lag_3'] = data[energy_col].shift(3).fillna(0)
        data['Energy_Lag_6'] = data[energy_col].shift(6).fillna(0)
        
        feature_cols.extend(['Energy_Lag_1', 'Energy_Lag_2', 'Energy_Lag_3', 'Energy_Lag_6'])
        
        # Скользящие средние
        data['Energy_MA_3'] = data[energy_col].rolling(window=3, min_periods=1).mean().fillna(0)
        data['Energy_MA_6'] = data[energy_col].rolling(window=6, min_periods=1).mean().fillna(0)
        data['Energy_MA_12'] = data[energy_col].rolling(window=12, min_periods=1).mean().fillna(0)
        
        feature_cols.extend(['Energy_MA_3', 'Energy_MA_6', 'Energy_MA_12'])
        
        # Убираем строки с NaN (первые 12 строк)
        data = data.fillna(0)
        
        # Сохраняем колонки
        self.feature_columns = feature_cols
        
        print(f"   Используемые признаки ({len(self.feature_columns)}): {self.feature_columns[:5]}...")
        
        X = data[self.feature_columns].values
        y = data[energy_col].values
        
        return X, y
    
    def train(self, df):
        """Обучение модели"""
        print("Подготовка признаков...")
        X, y = self.prepare_features(df)
        
        if X is None or len(X) < 50:
            print("   ❌ Недостаточно данных для обучения (нужно минимум 50)")
            return None, None
        
        # Разделение на train/test
        train_size = int(len(X) * 0.8)
        X_train, X_test = X[:train_size], X[train_size:]
        y_train, y_test = y[:train_size], y[train_size:]
        
        # Нормализация
        X_train_scaled = self.scaler.fit_transform(X_train)
        X_test_scaled = self.scaler.transform(X_test)
        
        # Простая и стабильная модель
        self.model = RandomForestRegressor(
            n_estimators=50,
            max_depth=8,
            min_samples_split=5,
            min_samples_leaf=2,
            random_state=42,
            n_jobs=1
        )
        
        print("   Обучение модели...")
        self.model.fit(X_train_scaled, y_train)
        
        # Оценка
        y_pred = self.model.predict(X_test_scaled)
        
        # Метрики
        mae = mean_absolute_error(y_test, y_pred)
        mse = mean_squared_error(y_test, y_pred)
        rmse = np.sqrt(mse)
        r2 = r2_score(y_test, y_pred)
        
        # MAPE (с защитой от нулей)
        y_test_safe = np.where(y_test < 0.1, 0.1, y_test)
        mape = np.mean(np.abs((y_test - y_pred) / y_test_safe)) * 100
        
        metrics = {
            'MAE': round(mae, 3),
            'RMSE': round(rmse, 3),
            'R2': round(r2, 3),
            'MAPE': round(mape, 1)
        }
        
        print(f"   ✅ Модель обучена!")
        print(f"      MAE: {metrics['MAE']} кВт·ч")
        print(f"      R²: {metrics['R2']}")
        
        self.is_trained = True
        
        return metrics, {'y_test': y_test, 'y_pred': y_pred}
    
    def predict_future(self, df, hours_ahead=24):
        """Прогнозирование на будущие часы"""
        # Если модель не обучена, возвращаем среднее
        if not self.is_trained or self.model is None:
            if 'energy_consumption' in df.columns:
                mean_val = df['energy_consumption'].mean()
            elif 'Energy Consumption (kWh)' in df.columns:
                mean_val = df['Energy Consumption (kWh)'].mean()
            else:
                mean_val = 2.5
            print(f"   ℹ️ Модель не обучена, использую среднее: {mean_val:.2f} кВт·ч")
            return [round(max(0.5, mean_val), 2)] * hours_ahead
        
        try:
            # Создаем последовательность для прогноза
            predictions = []
            
            # Базовые значения из последней записи
            last_record = df.iloc[-1:].copy()
            
            # Получаем текущие значения признаков
            current_features = {}
            for col in self.feature_columns:
                if col in last_record.columns:
                    current_features[col] = float(last_record[col].iloc[0])
                else:
                    current_features[col] = 0
            
            # Делаем прогноз пошагово
            for h in range(hours_ahead):
                # Создаем вектор признаков для текущего шага
                feature_vector = []
                
                for col in self.feature_columns:
                    if col == 'Hour':
                        # Час увеличивается
                        val = (current_features.get('Hour', 12) + h) % 24
                    elif col == 'DayOfWeek':
                        # День недели может меняться
                        val = (current_features.get('DayOfWeek', 3) + (h // 24)) % 7
                    elif col.startswith('Energy_Lag_'):
                        # Для лагов используем предыдущие предсказания
                        lag_num = int(col.split('_')[-1])
                        if len(predictions) >= lag_num:
                            val = predictions[-lag_num]
                        else:
                            val = current_features.get(col, 0)
                    elif col.startswith('Energy_MA_'):
                        # Для скользящих средних
                        window = int(col.split('_')[-1])
                        if len(predictions) >= window:
                            val = np.mean(predictions[-window:])
                        else:
                            val = current_features.get(col, current_features.get('Energy_MA_3', 2.5))
                    else:
                        # Остальные признаки
                        val = current_features.get(col, 0)
                    
                    feature_vector.append(val)
                
                # Нормализуем и предсказываем
                feature_vector_scaled = self.scaler.transform([feature_vector])
                pred = self.model.predict(feature_vector_scaled)[0]
                
                # Ограничиваем разумными значениями
                pred = max(0.2, min(10.0, pred))
                predictions.append(round(pred, 2))
            
            return predictions
            
        except Exception as e:
            print(f"   ⚠️ Ошибка в прогнозе: {e}")
            # Возвращаем среднее значение при ошибке
            if 'energy_consumption' in df.columns:
                mean_val = df['energy_consumption'].mean()
            else:
                mean_val = 2.5
            return [round(max(0.5, mean_val), 2)] * hours_ahead

    def save_model(self, filepath='models/energy_predictor.joblib'):
        """Сохранение модели"""
        import os
        os.makedirs('models', exist_ok=True)
        try:
            joblib.dump({
                'model': self.model,
                'scaler': self.scaler,
                'feature_columns': self.feature_columns,
                'is_trained': self.is_trained
            }, filepath)
            print(f"   💾 Модель сохранена")
            return True
        except Exception as e:
            print(f"   ⚠️ Ошибка сохранения: {e}")
            return False
    
    def load_model(self, filepath='models/energy_predictor.joblib'):
        """Загрузка модели"""
        import os
        if os.path.exists(filepath):
            try:
                saved = joblib.load(filepath)
                self.model = saved['model']
                self.scaler = saved['scaler']
                self.feature_columns = saved['feature_columns']
                self.is_trained = saved['is_trained']
                print("   ✅ Модель загружена")
                return True
            except Exception as e:
                print(f"   ⚠️ Ошибка загрузки: {e}")
                return False
        return False