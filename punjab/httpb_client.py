import hashlib
import random
import urlparse
import os

from twisted.internet import defer, reactor, protocol
from twisted.python import log, failure
try:
    from twisted.words.xish import domish, utility
except:
    from twisted.xish import domish, utility
from twisted.web import http

from twisted.words.protocols.jabber import xmlstream, client




from punjab.httpb import HttpbParse # maybe use something else to seperate from punjab

TLS_XMLNS = 'urn:ietf:params:xml:ns:xmpp-tls'
SASL_XMLNS = 'urn:ietf:params:xml:ns:xmpp-sasl'
BIND_XMLNS = 'urn:ietf:params:xml:ns:xmpp-bind'
SESSION_XMLNS = 'urn:ietf:params:xml:ns:xmpp-session'

NS_HTTP_BIND = "http://jabber.org/protocol/httpbind"

class Error(Exception):
    stanza_error = ''
    punjab_error = ''
    msg          = ''
    def __init__(self, msg = None):
        if msg:
            self.stanza_error = msg
            self.punjab_error = msg
            self.msg          = msg

    def __str__(self):
        return self.stanza_error


class RemoteConnectionFailed(Error):
    msg = 'remote-connection-failed'
    stanza_error = 'remote-connection-failed'


class NodeNotFound(Error):
    msg = '404 not found'

class NotAuthorized(Error):
    pass

class NotImplemented(Error):
    pass



# Exceptions raised by the client.
class HTTPBException(Exception): pass
class HTTPBNetworkTerminated(HTTPBException):
    def __init__(self, body_tag, elements):
        self.body_tag = body_tag
        self.elements = elements

    def __str__(self):
        return self.body_tag.toXml()



class XMPPAuthenticator(client.XMPPAuthenticator):
    """
    Authenticate against an xmpp server using BOSH
    """

class QueryProtocol(http.HTTPClient):
    noisy = False
    def connectionMade(self):
        self.factory.sendConnected(self)
        self.sendBody(self.factory.cb)

    def sendCommand(self, command, path):
        self.transport.write('%s %s HTTP/1.1\r\n' % (command, path))

    def sendBody(self, b, close = 0):
        if isinstance(b, domish.Element):
            bdata = b.toXml().encode('utf-8')
        else:
            bdata = b

        self.sendCommand('POST', self.factory.url)
        self.sendHeader('User-Agent', 'Twisted/XEP-0124')
        self.sendHeader('Host', self.factory.host)
        self.sendHeader('Content-type', 'text/xml')
        self.sendHeader('Content-length', str(len(bdata)))
        self.endHeaders()
        self.transport.write(bdata)

    def handleStatus(self, version, status, message):
        if status != '200':
            self.factory.badStatus(status, message)

    def handleResponse(self, contents):
        self.factory.parseResponse(contents, self)

    def lineReceived(self, line):
        if self.firstLine:
            self.firstLine = 0
            l = line.split(None, 2)
            version = l[0]
            status = l[1]
            try:
                message = l[2]
            except IndexError:
                # sometimes there is no message
                message = ""
            self.handleStatus(version, status, message)
            return
        if line:
            key, val = line.split(':', 1)
            val = val.lstrip()
            self.handleHeader(key, val)
            if key.lower() == 'content-length':
                self.length = int(val)
        else:
            self.__buffer = []
            self.handleEndHeaders()
            self.setRawMode()

    def handleResponseEnd(self):
        self.firstLine = 1
        if self.__buffer != None:
            b = ''.join(self.__buffer)

            self.__buffer = None
            self.handleResponse(b)

    def handleResponsePart(self, data):
        self.__buffer.append(data)


    def connectionLost(self, reason):
        #log.msg(dir(reason))
        #log.msg(reason)
        pass


class QueryFactory(protocol.ClientFactory):
    """ a factory to create http client connections.
    """
    deferred = None
    noisy = False
    protocol = QueryProtocol
    def __init__(self, url, host, b):
        self.url, self.host = url, host
        self.deferred = defer.Deferred()
        self.cb = b

    def send(self,b):
        self.deferred = defer.Deferred()

        self.client.sendBody(b)

        return self.deferred

    def parseResponse(self, contents, protocol):
        self.client = protocol
        hp = HttpbParse(True)

        try:
            body_tag,elements = hp.parse(contents)
        except:
            raise
        else:
            if body_tag.hasAttribute('type') and body_tag['type'] == 'terminate':
                error = failure.Failure(HTTPBNetworkTerminated(body_tag, elements))
                if self.deferred.called:
                    return defer.fail(error)
                else:
                    self.deferred.errback(error)
                return
            if self.deferred.called:
                return defer.succeed((body_tag,elements))
            else:
                self.deferred.callback((body_tag,elements))


    def sendConnected(self, q):
        self.q = q



    def clientConnectionLost(self, _, reason):
        try:
            self.client = None
            if not self.deferred.called:
                self.deferred.errback(reason)

        except:
            return reason

    clientConnectionFailed = clientConnectionLost

    def badStatus(self, status, message):
        if not self.deferred.called:
            self.deferred.errback(ValueError(status, message))




class Keys:
    """Generate keys according to XEP-0124 #15 "Protecting Insecure Sessions"."""
    def __init__(self):
        self.k = []

    def _set_keys(self):
        seed = os.urandom(1024)
        num_keys = random.randint(55,255)
        self.k = [hashlib.sha1(seed).hexdigest()]
        for i in xrange(num_keys-1):
            self.k.append(hashlib.sha1(self.k[-1]).hexdigest())

    def getKey(self):
        """
        Return (key, newkey), where key is the next key to use and newkey is the next
        newkey value to use.  If key or newkey are None, the next request doesn't require
        that value.
        """
        if not self.k:
            # This is the first call, so generate keys and only return new_key.
            self._set_keys()
            return None, self.k.pop()

        key = self.k.pop()

        if not self.k:
            # We're out of keys.  Regenerate keys and re-key.
            self._set_keys()
            return key, self.k.pop()

        return key, None


class Proxy:
    """A Proxy for making HTTP Binding calls.

    Pass the URL of the remote HTTP Binding server to the constructor.

    """

    def __init__(self, url):
        """
        Parse the given url and find the host and port to connect to.
        """
        parts = urlparse.urlparse(url)
        self.url = urlparse.urlunparse(('', '')+parts[2:])
        if self.url == "":
            self.url = "/"
        if ':' in parts[1]:
            self.host, self.port = parts[1].split(':')
            self.port = int(self.port)
        else:
            self.host, self.port = parts[1], None
        self.secure = parts[0] == 'https'

    def connect(self, b):
        """
        Make a connection to the web server and send along the data.
        """
        self.factory = QueryFactory(self.url, self.host, b)

        if self.secure:
            from twisted.internet import ssl
            self.rid = reactor.connectSSL(self.host, self.port or 443,
                                          self.factory, ssl.ClientContextFactory())
        else:
            self.rid = reactor.connectTCP(self.host, self.port or 80, self.factory)


        return self.factory.deferred


    def send(self,b):
        """ Send data to the web server. """

        # if keepalive is off we need a new query factory
        # TODO - put a check to reuse the factory, right now we open a new one.
        d = self.connect(b)
        return d

class HTTPBClientConnector:
    """
    A HTTP Binding client connector.
    """
    def __init__(self, url):
        self.url = url

    def connect(self, factory):
        self.proxy = Proxy(self.url)
        self.xs = factory.buildProtocol(self.proxy.host)
        self.xs.proxy = self.proxy
        self.xs.connectionMade()


    def disconnect(self):
        self.xs.connectionLost('disconnect')
        self.xs = None


class HTTPBindingStream(xmlstream.XmlStream):
    """
    HTTP Binding wrapper that acts like xmlstream

    """

    def __init__(self, authenticator):
        xmlstream.XmlStream.__init__(self, authenticator)
        self.base_url = '/xmpp-httpbind/'
        self.host = 'dev.chesspark.com'
        self.mechanism = 'PLAIN'
        # request id
        self.rid = random.randint(0, 10000000)
        # session id
        self.session_id = 0
        # keys
        self.keys = Keys()
        self.initialized = False
        self.requests = []

    def _cbConnect(self, result):
        r,e = result
        ms = ''
        self.initialized = True
        # log.msg('======================================== cbConnect ====================')
        self.session_id = r['sid']
        self.authid = r['authid']
        self.namespace = self.authenticator.namespace
        self.otherHost = self.authenticator.otherHost
        self.dispatch(self, xmlstream.STREAM_START_EVENT)
        # Setup observer for stream errors
        self.addOnetimeObserver("/error[@xmlns='%s']" % xmlstream.NS_STREAMS,
                                self.onStreamError)

        if len(e)>0 and e[0].name == 'features':
            # log.msg('============================= on features ==============================')
            self.onFeatures(e[0])
        else:
            self.authenticator.streamStarted()

    def _ebError(self, e):
        log.err(e.printTraceback())


    def _initializeStream(self):
        """ Initialize binding session.

        Just need to create a session once, this can be done elsewhere, but here will do for now.
        """

        if not self.initialized:
            b = domish.Element((NS_HTTP_BIND,'body'))

            b['content']  = 'text/xml; charset=utf-8'
            b['hold']     = '1'
            b['rid']      = str(self.rid)
            b['to']       = self.authenticator.jid.host
            b['wait']     = '60'
            b['xml:lang'] = 'en'
            # FIXME - there is an issue with the keys
            # b = self.key(b)

            # Connection test
            d = self.proxy.connect(b)
            d.addCallback(self._cbConnect)
            d.addErrback(self._ebError)
            return d
        else:
            self.authenticator.initializeStream()


    def key(self,b):
        key, newkey = self.keys.getKey()

        if key:
            b['key'] = key
        if newkey:
            b['newkey'] = newkey

    def _cbSend(self, result):
        body, elements = result
        if body.hasAttribute('type') and body['type'] == 'terminate':
            reactor.close()
        self.requests.pop(0)
        for e in elements:
            if self.rawDataInFn:
                self.rawDataInFn(str(e.toXml()))
            if e.name == 'features':
                self.onFeatures(e)
            else:
                self.onElement(e)
        # if no elements lets send out another poll
        if len(self.requests)==0:
            self.send()


    def send(self, obj = None):
        if self.session_id == 0:
            return defer.succeed(False)

        b = domish.Element((NS_HTTP_BIND,"body"))
        b['content']  = 'text/xml; charset=utf-8'
        self.rid = self.rid + 1
        b['rid']      = str(self.rid)
        b['sid']      = str(self.session_id)
        b['xml:lang'] = 'en'

        if obj is not None:
            if domish.IElement.providedBy(obj):
                if self.rawDataOutFn:
                    self.rawDataOutFn(str(obj.toXml()))
                b.addChild(obj)
        #b = self.key(b)
        self.requests.append(b)
        d = self.proxy.send(b)
        d.addCallback(self._cbSend)
        return d


class HTTPBindingStreamFactory(xmlstream.XmlStreamFactory):
    """
    Factory for HTTPBindingStream protocol objects.
    """

    def buildProtocol(self, _):
        self.resetDelay()
        xs = HTTPBindingStream(self.authenticator)
        xs.factory = self
        for event, fn in self.bootstraps: xs.addObserver(event, fn)
        return xs

