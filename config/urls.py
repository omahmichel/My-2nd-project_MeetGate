from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/accounts/", include("accounts.urls")),
    path("api/meetings/", include("meetings.urls")),
   path("api/zoom/", include("zoom_integration.urls")),
]
