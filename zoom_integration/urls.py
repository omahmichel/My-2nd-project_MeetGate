from django.urls import path

from .views import (
    ZoomCallbackView,
    ZoomConnectionStatusView,
    ZoomLoginView,
)


urlpatterns = [
    path("login/", ZoomLoginView.as_view(), name="zoom-login"),
    path("callback/", ZoomCallbackView.as_view(), name="zoom-callback"),
    path(
        "status/",
        ZoomConnectionStatusView.as_view(),
        name="zoom-connection-status",
    ),
]