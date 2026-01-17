import requests

url = "http://127.0.0.1:11435/v1/models"
print(f"Testing connection to {url}...")

try:
    response = requests.get(url)
    print(f"Status Code: {response.status_code}")
    print("Response:")
    print(response.json())
except Exception as e:
    print(f"Error: {e}")
