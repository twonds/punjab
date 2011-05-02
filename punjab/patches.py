# XXX: All monkey patches should be sent upstream and eventually removed.

import functools

def patch(cls, attr):
    """Patch the function named attr in the object cls with the decorated function."""
    orig_func = getattr(cls, attr)
    @functools.wraps(orig_func)
    def decorator(func):
        def wrapped_func(*args, **kwargs):
            return func(orig_func, *args, **kwargs)
        setattr(cls, attr, wrapped_func)
        return orig_func
    return decorator

# Modify jabber.error.exceptionFromStreamError to include the XML element in
# the exception.
from twisted.words.protocols.jabber import error as jabber_error
@patch(jabber_error, "exceptionFromStreamError")
def exceptionFromStreamError(orig, element):
    exception = orig(element)
    exception.element = element
    return exception

