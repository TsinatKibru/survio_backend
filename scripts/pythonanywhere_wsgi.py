import os
import sys
from dotenv import load_dotenv

# Path to your project directory (now that it's a standalone repo)
project_home = '/home/alexpsycht/Survio'
if project_home not in sys.path:
    sys.path.append(project_home)

# Load environment variables from .env file
load_dotenv(os.path.join(project_home, '.env'))

os.environ['DJANGO_SETTINGS_MODULE'] = 'survio.settings'

from django.core.wsgi import get_wsgi_application
application = get_wsgi_application()
