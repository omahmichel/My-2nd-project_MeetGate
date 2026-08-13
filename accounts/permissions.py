from rest_framework.permissions import BasePermission


class IsMobileVerified(BasePermission):
    """Allow authenticated users only after mobile verification."""

    message = "Verify your mobile number before accessing this feature."

    def has_permission(self, request, view):
        # Authentication is checked separately; missing profiles fail closed.
        user = request.user

        if not user or not user.is_authenticated:
            return False

        profile = getattr(user, "profile", None)

        return bool(
            profile
            and profile.mobile_verified
        )
