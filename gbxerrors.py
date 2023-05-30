class ValidationError(BaseException):
    """
    Raised when the validation function fails
    """


class GBXWriteError(BaseException):
    """
    Raised when failed to write the Gbx file.
    """