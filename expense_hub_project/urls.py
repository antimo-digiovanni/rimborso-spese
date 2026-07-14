from django.contrib import admin
from django.conf import settings
from django.urls import include, path, re_path

from claims import views as claim_views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('manifest.webmanifest', claim_views.manifest, name='manifest'),
    path('service-worker.js', claim_views.service_worker, name='service_worker'),
    re_path(r'^media/(?P<path>.*)$', claim_views.media_file, name='media_file'),
    path('', include('claims.urls')),
]
