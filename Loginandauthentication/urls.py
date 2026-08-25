from django.urls import path

from .editProfile import changeEmail
from .views import EarlyRegisterUserView, to_be_notified_email, ResendOtpView, VerifyOTPView, AndroidRequestOtpView
from .views import PostOtpView
from .editprofileView import changePhone, changeSecondName, changeFirstName, changeEmail

urlpatterns =[
    path('register/', EarlyRegisterUserView.as_view(), name='register'),
    path('postotp/', PostOtpView.as_view(), name='post_otp'),
    path('nofityemail/', to_be_notified_email.as_view(), name='notified_email'),
    path('resendotp/', ResendOtpView.as_view(), name='resend_otp'),
    path('verify/', VerifyOTPView.as_view(), name="verify-otp"),
    path('changeFname/', changeFirstName.as_view(), name="changeFName"),
    path('changeSName/', changeSecondName.as_view(), name="changeSName"),
    path('api/changeEmail/', changeEmail.as_view(), name="changeEmail"),
    path('changePhoneNumber/', changePhone.as_view(), name="changePhoneNumber"),
path('androidLogin/',AndroidRequestOtpView.as_view(), name="changePhoneNumber"),



]