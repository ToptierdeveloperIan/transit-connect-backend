class RedeemError(Exception):
    def __init__(self, message, code="invalid_code", status_code=400):
        super().__init__(message)
        self.message = message
        self.code = code
        self.status_code = status_code
