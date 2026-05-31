
import requests
import json

def test_api():
    """Тестирование API endpoints"""
    base_url = "http://localhost:5000"
    
    endpoints = [
        '/api/status',
        '/api/dashboard_data',
        '/api/energy_timeseries',
        '/api/alerts'
    ]
    
    for endpoint in endpoints:
        try:
            response = requests.get(f"{base_url}{endpoint}")
            print(f"\n{endpoint}:")
            print(f"  Status: {response.status_code}")
            if response.status_code == 200:
                data = response.json()
                if 'error' in data:
                    print(f"  Error: {data['error']}")
                else:
                    print(f"  ✅ OK - {len(str(data))} bytes")
            else:
                print(f"  ❌ Error: {response.text[:200]}")
        except Exception as e:
            print(f"  ❌ Connection error: {e}")

if __name__ == "__main__":
    test_api()