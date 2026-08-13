from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView

from .views import (
    GoogleAuthView,
    GoogleClientConfigView,
    LoginView,
    RegisterView,
    SendMobileOTPView,
    VerifyMobileOTPView,
)

urlpatterns = [
    path("register/", RegisterView.as_view(), name="register"),
    path("login/", LoginView.as_view(), name="login"),
    path(
        "google/config/",
        GoogleClientConfigView.as_view(),
        name="google-auth-config",
    ),
    path("google/", GoogleAuthView.as_view(), name="google-auth"),
    path("token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("mobile/send-otp/", SendMobileOTPView.as_view(), name="mobile-send-otp"),
    path("mobile/verify-otp/", VerifyMobileOTPView.as_view(), name="mobile-verify-otp"),
]
