from django.urls import path

from Loginandauthentication.urls import urlpatterns

urlpatterns = [
    path('verify/', VerifyOTPView.as_view(), name="verify-otp"),
]