import urllib.request, json, urllib.error
req = urllib.request.Request(
    'http://localhost:8000/api/auth/login',
    data=json.dumps({'username': 'admin', 'password': 'changeme'}).encode('utf-8'),
    headers={'Content-Type': 'application/json'}
)
try:
    urllib.request.urlopen(req)
except urllib.error.HTTPError as e:
    print("HTTPError:", e.code)
    print(e.read().decode('utf-8'))
