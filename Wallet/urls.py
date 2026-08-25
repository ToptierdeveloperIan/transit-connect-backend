from django.urls import path

from .views import (
    WalletBalanceView,
    WalletDepositView,
    WalletHealthView,
    WalletIntentsView,
    WalletLedgerView,
    WalletSpendView,
)

urlpatterns = [
    path("health/", WalletHealthView.as_view(), name="wallet-health"),
    path("balance/", WalletBalanceView.as_view(), name="wallet-balance"),
    path("ledger/", WalletLedgerView.as_view(), name="wallet-ledger"),
    path("intents/", WalletIntentsView.as_view(), name="wallet-intents"),
    path("deposits/", WalletDepositView.as_view(), name="wallet-deposits"),
    path("spend/", WalletSpendView.as_view(), name="wallet-spend"),
]
