import requests
import json
import time

# Test the streaming endpoint
url = "http://127.0.0.1:8000/api/nlp/chat/answer"
headers = {"Content-Type": "application/json"}
data = {"question": "hello"}

print("Testing streaming endpoint...")
print(f"URL: {url}")
print(f"Data: {data}\n")

try:
    response = requests.post(url, headers=headers, json=data, stream=True, timeout=10)
    print(f"Status Code: {response.status_code}")
    print(f"Content-Type: {response.headers.get('Content-Type')}")
    print(f"Headers: {dict(response.headers)}\n")
    
    print("Response body (first 1000 chars):")
    content = response.text[:1000]
    print(content)
    
    if "data:" in content:
        print("\n✓ Response contains SSE format!")
    else:
        print("\n✗ Response does NOT contain SSE format")
        
except Exception as e:
    print(f"Error: {e}")
