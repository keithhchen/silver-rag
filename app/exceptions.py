class ServiceError(Exception):
    def __init__(self, message: str, status_code: int = 500):
        super().__init__(message)
        self.status_code = status_code

class StorageError(ServiceError):
    pass

class UpstageAPIError(ServiceError):
    pass

class DifyAPIError(ServiceError):
    pass

class DatabaseError(ServiceError):
    pass