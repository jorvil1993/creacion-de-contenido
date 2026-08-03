import re
import urllib.request
import json

url = 'https://deviceshopbo.com/productos.js'
req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
content = urllib.request.urlopen(req).read().decode('utf-8')

products = []
for m in re.finditer(r'id:\s*"([^"]+)",\s*nombre:\s*"([^"]+)"', content):
    products.append({'id': m.group(1), 'nombre': m.group(2)})

for p in products:
    print(f"{p['id']}: {p['nombre']}")
