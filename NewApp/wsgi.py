import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'NewApp.settings')  # Remplacez 'NewApp' par le nom de votre projet

application = get_wsgi_application()