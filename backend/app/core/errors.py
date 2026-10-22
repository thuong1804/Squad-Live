class DomainError(Exception):
    def __init__(self, status: int, code: str, message: str):
        self.status = status
        self.code = code
        self.message = message


def conflict(message: str):
    raise DomainError(409, "conflict", message)
