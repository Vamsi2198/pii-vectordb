import urllib.request
import urllib.error

url = 'http://127.0.0.1:8001/api/run-demo'
req = urllib.request.Request(url, method='POST')
try:
    with urllib.request.urlopen(req, timeout=30) as r:
        print('STATUS', r.status)
        print(r.read().decode())
except urllib.error.HTTPError as e:
    print('HTTPERROR', e.code)
    print(e.read().decode())
except Exception as e:
    print('ERROR', e)
