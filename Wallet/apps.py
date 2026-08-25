from django.apps import AppConfig


class WalletConfig(AppConfig):
    """
    In-app wallet for rider balances.

    Owns ledger truth, deposit intents (M-Pesa / Airtel Money rails),
    and spend that only commits after canonical provider success (or explicit
    internal settle after provider-confirmed funding).

    Does not re-price fares — pay amounts come from FareQuote.discounted_fare
    via paymentSystem.fare_bridge.
    """

    default_auto_field = "django.db.models.BigAutoField"
    name = "Wallet"
    verbose_name = "Wallet"
