import urllib.request

try:
    with urllib.request.urlopen('http://127.0.0.1:8000/api/status', timeout=5) as r:
        print(r.status)
        print(r.read().decode())
except Exception as e:
    print('ERROR', e)
