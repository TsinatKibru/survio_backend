import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'survio.settings')
django.setup()

from django.test import Client
from accounts.models import User

c = Client(enforce_csrf_checks=False)
admin_user = User.objects.filter(username='admin').first()
if not admin_user:
    print("No superuser found")
    exit(1)

c.force_login(admin_user)
response = c.get('/admin/', HTTP_HOST='127.0.0.1')

if response.status_code == 500:
    import re
    match = re.search(r'(?s)<textarea id=\"traceback_area\".*?>(.*?)</textarea>', response.content.decode('utf-8'))
    if match:
        print(match.group(1).replace('&amp;', '&').replace('&lt;', '<').replace('&gt;', '>'))
    else:
        print("500 Error, but no traceback textarea found.")
        print(response.content.decode('utf-8')[:2000])
else:
    print(f"Status Code: {response.status_code}")
