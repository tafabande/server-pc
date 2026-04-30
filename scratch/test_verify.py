import urllib.request, urllib.error
req = urllib.request.Request('http://localhost:8000/api/auth/verify')
try:
    urllib.request.urlopen(req)
except urllib.error.HTTPError as e:
    print("HTTPError:", e.code)
    print(e.read().decode('utf-8'))
