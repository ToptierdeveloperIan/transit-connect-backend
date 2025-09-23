from django.urls import path
from .views import EarlyRegisterUserView, to_be_notified_email, ResendOtpView, VerifyOTPView
from .views import PostOtpView

urlpatterns =[
    path('register/', EarlyRegisterUserView.as_view(), name='register'),
    path('postotp/', PostOtpView.as_view(), name='post_otp'),
    path('nofityemail/', to_be_notified_email.as_view(), name='notified_email'),
    path('resendotp/', ResendOtpView.as_view(), name='resend_otp'),
    path('verify/', VerifyOTPView.as_view(), name="verify-otp"),

]