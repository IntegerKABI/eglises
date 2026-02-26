"""
=================================================================
URLS PRINCIPALES — Point d'entrée du routage
=================================================================
Ce fichier inclut :
1. L'admin Django (/admin/)
2. Les URLs de notre app church
3. Les URLs d'authentification (login/logout)
4. La configuration pour servir les fichiers média en développement
=================================================================
"""

from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.contrib.auth import views as auth_views

urlpatterns = [
    # Admin Django intégré
    path('admin/', admin.site.urls),

    # Authentification (login / logout)
    path('login/', auth_views.LoginView.as_view(template_name='registration/login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),

    # Notre application church (toutes les autres URLs)
    path('', include('church.urls')),
]

# En mode DEBUG, Django sert les fichiers média (images uploadées)
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
