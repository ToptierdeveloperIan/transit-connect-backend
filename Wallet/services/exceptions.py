"""Domain errors for Wallet. Views map to HTTP envelopes."""


class WalletError(Exception):
    code = "wallet_error"
    status = 400

    def __init__(self, message: str, code: str | None = None, status: int | None = None):
        super().__init__(message)
        self.message = message
        if code:
            self.code = code
        if status is not None:
            self.status = status


class InsufficientFundsError(WalletError):
    code = "insufficient_funds"
    status = 402


class IntentStateError(WalletError):
    code = "intent_state_error"
    status = 409


class IdempotencyError(WalletError):
    code = "idempotency_conflict"
    status = 409


class AmountMismatchError(WalletError):
    code = "amount_mismatch"
    status = 400
