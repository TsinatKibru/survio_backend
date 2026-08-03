import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'survio.settings')
django.setup()

from django.test import Client
from accounts.models import User

client = Client()
# Log the user in to populate the session
user = User.objects.get(username='admin')
client.force_login(user)

# Call the API endpoint
response = client.get('/api/submissions/export-compliance-pdf/')
print("Response status code:", response.status_code)
if response.status_code != 200:
    print("Response data:", response.content)
