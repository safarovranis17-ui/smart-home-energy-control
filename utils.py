import numpy as np
import pandas as pd

def calculate_predictive_amortization(df, predictions, device_usage_stats):
    """
    Расчет предиктивной амортизации
    """
    # Если данных недостаточно, возвращаем значения по умолчанию
    if df is None or len(df) < 10:
        return get_default_amortization()
    
    appliances = ['Television', 'Dryer', 'Oven', 'Refrigerator', 'Microwave']
    
    # Весовые коэффициенты важности приборов
    importance_weights = {
        'Television': 0.15,
        'Dryer': 0.25,
        'Oven': 0.25,
        'Refrigerator': 0.30,
        'Microwave': 0.05
    }
    
    # Прогнозируемая средняя нагрузка
    if predictions and len(predictions) > 0:
        predicted_avg_load = np.mean(predictions)
    else:
        predicted_avg_load = df['energy_consumption'].mean() if 'energy_consumption' in df.columns else 2.5
    
    max_load = df['energy_consumption'].max() if 'energy_consumption' in df.columns else 5.0
    
    # Коэффициент нагрузки
    load_factor = predicted_avg_load / max_load if max_load > 0 else 0.5
    
    results = {}
    total_amortization = 0
    
    for appliance in appliances:
        # Получаем статистику использования
        if appliance in device_usage_stats:
            usage_freq = device_usage_stats[appliance].get('active_percentage', 20) / 100
            avg_energy = device_usage_stats[appliance].get('avg_energy_when_on', 2.0)
        else:
            usage_freq = 0.2
            avg_energy = 2.0
        
        # Важность прибора
        importance = importance_weights.get(appliance, 0.2)
        
        # Прогнозируемый износ
        predicted_wear = load_factor * (usage_freq + 0.1)
        
        # Предиктивная амортизация
        amortization = (load_factor * 0.4 + usage_freq * 0.3 + importance * 0.3) * predicted_wear * 100
        amortization = min(100, max(0, amortization))  # Ограничиваем 0-100
        
        results[appliance] = {
            'amortization_score': round(amortization, 2),
            'usage_frequency': round(usage_freq * 100, 1),
            'load_factor': round(load_factor, 3),
            'importance_weight': importance,
            'status': get_amortization_status(amortization)
        }
        
        total_amortization += amortization * importance
    
    # Нормализуем общую амортизацию
    total_amortization = min(100, total_amortization / sum(importance_weights.values()))
    
    results['total'] = {
        'amortization_score': round(total_amortization, 2),
        'predicted_avg_load': round(predicted_avg_load, 2),
        'peak_load': round(max_load, 2),
        'status': get_amortization_status(total_amortization)
    }
    
    return results


def get_default_amortization():
    """Возвращает значения амортизации по умолчанию (когда данных недостаточно)"""
    appliances = ['Television', 'Dryer', 'Oven', 'Refrigerator', 'Microwave']
    
    results = {}
    for appliance in appliances:
        results[appliance] = {
            'amortization_score': 25.0,
            'usage_frequency': 20.0,
            'load_factor': 0.5,
            'importance_weight': 0.2,
            'status': {'text': 'Хорошее', 'color': 'lightgreen', 'icon': '🟢'}
        }
    
    results['total'] = {
        'amortization_score': 25.0,
        'predicted_avg_load': 2.5,
        'peak_load': 5.0,
        'status': {'text': 'Хорошее', 'color': 'lightgreen', 'icon': '🟢'}
    }
    
    return results


def get_amortization_status(score):
    """Статус амортизации на основе score"""
    if score < 20:
        return {'text': 'Отличное', 'color': 'green', 'icon': '✅'}
    elif score < 40:
        return {'text': 'Хорошее', 'color': 'lightgreen', 'icon': '🟢'}
    elif score < 60:
        return {'text': 'Удовлетворительное', 'color': 'yellow', 'icon': '⚠️'}
    elif score < 80:
        return {'text': 'Требует внимания', 'color': 'orange', 'icon': '🔴'}
    else:
        return {'text': 'Критическое', 'color': 'red', 'icon': '‼️'}


def generate_alerts(df, predictions, amortization_results):
    """Генерация предупреждений и рекомендаций"""
    alerts = []
    recommendations = []
    
    if not amortization_results or 'total' not in amortization_results:
        return alerts, recommendations
    
    # Проверка критической амортизации
    total_status = amortization_results['total']['status']['text']
    if total_status == 'Критическое':
        alerts.append({
            'type': 'critical',
            'message': 'КРИТИЧЕСКАЯ АМОРТИЗАЦИЯ! Требуется немедленное обслуживание системы.',
            'icon': '🚨'
        })
    elif total_status == 'Требует внимания':
        alerts.append({
            'type': 'warning',
            'message': 'Внимание! Амортизация системы достигла высокого уровня. Рекомендуется проверить оборудование.',
            'icon': '⚠️'
        })
    
    # Проверка приборов с высокой амортизацией
    for appliance, data in amortization_results.items():
        if appliance != 'total' and data.get('status', {}).get('text') == 'Критическое':
            alerts.append({
                'type': 'warning',
                'message': f'Прибор "{appliance}" требует обслуживания (амортизация: {data["amortization_score"]}%)',
                'icon': '🔧'
            })
    
    # Рекомендации
    if df is not None and len(df) > 0:
        # Анализ времени пикового потребления
        if 'hour' in df.columns:
            peak_hour = df.groupby('hour')['energy_consumption'].mean().idxmax()
            recommendations.append({
                'title': 'Оптимизация времени использования',
                'description': f'Пик энергопотребления приходится на {peak_hour}:00. Рекомендуется перенести работу энергоемких приборов на другие часы.'
            })
    
    # Экономический эффект
    if predictions and len(predictions) > 0 and df is not None and len(df) > 0:
        avg_daily_consumption = df['energy_consumption'].mean() * 24 if 'energy_consumption' in df.columns else 60
        predicted_daily = np.mean(predictions) * 24
        potential_savings = (avg_daily_consumption - predicted_daily) * 30 * 5  # 5 руб/кВт·ч
        
        if potential_savings > 50:
            recommendations.append({
                'title': 'Экономический потенциал',
                'description': f'При оптимизации энергопотребления возможна экономия до {potential_savings:.0f} руб./месяц.'
            })
    
    return alerts, recommendations