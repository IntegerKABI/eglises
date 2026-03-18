"""
=================================================================
URLS PRINCIPALES - Point d'entree du routage
=================================================================
Ce fichier inclut :
1. L'admin Django (/admin/)
2. Les URLs de notre app church
3. Les URLs d'authentification (login/logout)
4. La configuration pour servir les fichiers media en developpement
=================================================================
"""

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import include, path
from church.views import TenantLoginView

urlpatterns = [
    path('admin/', admin.site.urls),
    path('login/', TenantLoginView.as_view(), name='login'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
    path('', include('church.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
