from django.urls import path

from .views import RedeemCodeValidation


urlpatterns = [
    path("redeem-code/validate/", RedeemCodeValidation.as_view(), name="RedeemCodeValidation"),
]
