from django.urls import path

from .views import (
    PhoneChangeConfirmView,
    PhoneChangeRequestView,
    ProfileDetailView,
    UpdateNameView,
    UserSettingsHealthView,
)

urlpatterns = [
    path("health/", UserSettingsHealthView.as_view(), name="user-settings-health"),
    # Profile snapshot
    path("profile/", ProfileDetailView.as_view(), name="user-settings-profile"),
    # Non-sensitive: names (online + offline-queue replay)
    path("profile/name/", UpdateNameView.as_view(), name="user-settings-name"),
    # Sensitive: phone OTP state machine (online only)
    path(
        "profile/phone/request/",
        PhoneChangeRequestView.as_view(),
        name="user-settings-phone-request",
    ),
    path(
        "profile/phone/confirm/",
        PhoneChangeConfirmView.as_view(),
        name="user-settings-phone-confirm",
    ),
]
