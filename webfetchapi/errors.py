class UpstreamError(Exception):
    def __init__(self, message, status=502, code='upstream_error'):
        self.message, self.status, self.code = message, status, code
        super().__init__(message)
