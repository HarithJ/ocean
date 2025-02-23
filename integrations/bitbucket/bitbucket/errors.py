from port_ocean.exceptions.core import OceanAbortException


class BitbucketTokenNotFoundException(OceanAbortException):
    pass


class BitbucketTooManyTokensException(OceanAbortException):
    def __init__(self):
        super().__init__(
            "There are too many tokens in tokenMapping. When using webhook configuration,"
            " there should be only one token configured"
        )


class BitbucketEventListenerConflict(OceanAbortException):
    pass


class BitbucketIllegalEventName(OceanAbortException):
    pass
