from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    # Inclure les URLs de l'application chat
    path('api/chat/', include('chat.urls')),
]