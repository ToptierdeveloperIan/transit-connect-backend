from django.urls import path
from .views import (
    InitiateSTKPushView,
    STKPushCallbackView,
    InitiateB2CView,
    B2CResultView,
    B2CTimeoutView,
)

urlpatterns = [
    # STK Push (C2B) — rider pays for ride
    path('payments/stk/initiate/', InitiateSTKPushView.as_view(), name='stk_initiate'),
    path('payments/stk/callback/', STKPushCallbackView.as_view(), name='stk_callback'),

    # B2C — business pays customer/driver
    path('payments/b2c/initiate/', InitiateB2CView.as_view(), name='b2c_initiate'),
    path('payments/b2c/result/', B2CResultView.as_view(), name='b2c_result'),
    path('payments/b2c/timeout/', B2CTimeoutView.as_view(), name='b2c_timeout'),
]
