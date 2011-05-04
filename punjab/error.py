""" Error class for different punjab parts. """


class Error(Exception):
    stanza_error = ''
    punjab_error = ''
    msg          = ''
    children     = []
    def __init__(self,msg = None):
        Exception.__init__(self)
        if msg:
            self.stanza_error = msg
            self.punjab_error = msg
            self.msg          = msg

    def __str__(self):
        return self.stanza_error

class BadRequest(Error):
    stanza_error = 'bad-request'
    msg = 'bad-request'

class InternalServerError(Error):
    msg = 'internal-server-error'
    stanza_error = 'internal-server-error'

class RemoteConnectionFailed(Error):
    msg = 'remote-connection-failed'
    stanza_error = 'remote-connection-failed'

class NotFound(Error):
    msg = '404 not found'
    stanza_error = 'not-found'

class NotAuthorized(Error):
    pass

class NotImplemented(Error):
    pass


NS_XMPP_STANZAS = "urn:ietf:params:xml:ns:xmpp-stanzas"

conditions = {
    'bad-request':		{'code': '400', 'type': 'modify'},
    'not-authorized':		{'code': '401', 'type': 'cancel'},
    'forbidden':		{'code': '403', 'type': 'cancel'},
    'not-found':		{'code': '404', 'type': 'cancel'},
    'not-acceptable':		{'code': '406', 'type': 'modify'},
    'conflict':			{'code': '409', 'type': 'cancel'},
    'internal-server-error':	{'code': '500', 'type': 'wait'},
    'feature-not-implemented':  {'code': '501', 'type': 'cancel'},
    'service-unavailable':	{'code': '503', 'type': 'cancel'},
    'host-gone':		{'code': '200', 'type': 'terminate'},
    'host-unknown':		{'code': '200', 'type': 'terminate'},
    'improper-addressing':	{'code': '200', 'type': 'terminate'},
    'other-request':	{'code': '200', 'type': 'terminate'},
    'remote-connection-failed':	{'code': '200', 'type': 'terminate'},
    'remote-stream-error':	{'code': '200', 'type': 'terminate'},
    'see-other-uri':	{'code': '200', 'type': 'terminate'},
    'system-shutdown':	{'code': '200', 'type': 'terminate'},
    'undefined-condition':	{'code': '200', 'type': 'terminate'},
    'item-not-found':		{'code': '200', 'type': 'terminate'},

}

