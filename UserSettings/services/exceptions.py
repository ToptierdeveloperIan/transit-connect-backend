"""Domain errors for UserSettings. Views map these to HTTP envelopes."""


class SettingsError(Exception):
    code = "settings_error"
    status = 400

    def __init__(self, message: str, code: str | None = None, status: int | None = None):
        super().__init__(message)
        self.message = message
        if code:
            self.code = code
        if status is not None:
            self.status = status


class ConflictError(SettingsError):
    code = "version_conflict"
    status = 409


class ValidationError(SettingsError):
    code = "validation_error"
    status = 400


class PhoneTakenError(SettingsError):
    code = "phone_taken"
    status = 409


class ChallengeError(SettingsError):
    code = "challenge_error"
    status = 400
