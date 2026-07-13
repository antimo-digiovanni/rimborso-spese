from django.contrib import admin
from django.conf import settings
from django.conf.urls.static import static
from django.urls import include, path

from claims import views as claim_views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('manifest.webmanifest', claim_views.manifest, name='manifest'),
    path('service-worker.js', claim_views.service_worker, name='service_worker'),
    path('', include('claims.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
