import os

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from accounts.models import AccountProfile


class Command(BaseCommand):
    help = "Create or repair the permanent MeetGate production administrator."

    def handle(self, *args, **options):
        # Read administrator credentials from environment variables only.
        admin_email = os.getenv("MEETGATE_ADMIN_EMAIL", "").strip().lower()
        admin_password = os.getenv("MEETGATE_ADMIN_PASSWORD", "").strip()
        admin_first_name = os.getenv(
            "MEETGATE_ADMIN_FIRST_NAME",
            "MeetGate",
        ).strip()
        admin_last_name = os.getenv(
            "MEETGATE_ADMIN_LAST_NAME",
            "Admin",
        ).strip()

        if not admin_email:
            raise CommandError(
                "MEETGATE_ADMIN_EMAIL environment variable is required."
            )

        if not admin_password:
            raise CommandError(
                "MEETGATE_ADMIN_PASSWORD environment variable is required."
            )

        User = get_user_model()

        # Use the email as both username and email to match MeetGate's
        # existing registration convention.
        user, created = User.objects.get_or_create(
            username=admin_email,
            defaults={
                "email": admin_email,
                "first_name": admin_first_name,
                "last_name": admin_last_name,
            },
        )

        # Keep the designated administrator account permanently usable.
        user.email = admin_email
        user.first_name = admin_first_name
        user.last_name = admin_last_name
        user.is_active = True
        user.is_staff = True
        user.is_superuser = True

        # Update the password from the secured Render environment value.
        user.set_password(admin_password)
        user.save()

        # Ensure the administrator also has the profile expected by MeetGate.
        profile, _ = AccountProfile.objects.get_or_create(
            user=user,
            defaults={
                "account_type": "host",
                "phone_number": "",
                "mobile_verified": True,
            },
        )

        # Repair an existing profile if necessary.
        profile.account_type = "host"
        profile.mobile_verified = True
        profile.save(
            update_fields=[
                "account_type",
                "mobile_verified",
                "updated_at",
            ]
        )

        action = "created" if created else "updated"

        self.stdout.write(
            self.style.SUCCESS(
                f"MeetGate administrator {action} successfully: "
                f"{admin_email}"
            )
        )
