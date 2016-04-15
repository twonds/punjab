# punjab's jabber client
from twisted.internet import reactor, error
from twisted.words.protocols.jabber import client, jid
from twisted.python import log
from copy import deepcopy

from twisted.words.xish import domish
from twisted.words.protocols.jabber import xmlstream
from punjab.xmpp.ns import XMPP_PREFIXES


INVALID_USER_EVENT = "//event/client/basicauth/invaliduser"
AUTH_FAILED_EVENT = "//event/client/basicauth/authfailed"
REGISTER_FAILED_EVENT = "//event/client/basicauth/registerfailed"

# event funtions


def basic_connect(jabberid, secret, host, port, cb, v=0):
    myJid = jid.JID(jabberid)
    factory = client.basicClientFactory(myJid, secret)
    factory.v = v
    factory.addBootstrap('//event/stream/authd', cb)
    reactor.connectTCP(host, port, factory)
    return factory


def basic_disconnect(f, xmlstream):
    sh = "</stream:stream>"
    xmlstream.send(sh)
    f.stopTrying()
    xmlstream = None


class JabberClientFactory(xmlstream.XmlStreamFactory):
    def __init__(self, host, v=0):
        """ Initialize
        """
        p = self.authenticator = PunjabAuthenticator(host)
        xmlstream.XmlStreamFactory.__init__(self, p)

        self.pending = {}
        self.maxRetries = 2
        self.host = host
        self.jid = ""
        self.raw_buffer = ""

        if v != 0:
            self.v = v
            self.rawDataOutFn = self.rawDataOut
            self.rawDataInFn = self.rawDataIn

    def clientConnectionFailed(self, connector, reason, d=None):
        if self.continueTrying:
            self.connector = connector
            if not reason.check(error.UserError):
                self.retry()
            if self.maxRetries and (self.retries > self.maxRetries):
                if d:
                    d.errback(reason)

    def rawDataIn(self, buf):
        log.msg("RECV: %s" % unicode(buf, 'utf-8').encode('ascii', 'replace'))

    def rawDataOut(self, buf):
        log.msg("SEND: %s" % unicode(buf, 'utf-8').encode('ascii', 'replace'))


class PunjabAuthenticator(xmlstream.ConnectAuthenticator):
    namespace = "jabber:client"
    version = '1.0'
    useTls = 1

    def connectionMade(self):
        host = self.otherHost
        self.streamHost = host

        self.xmlstream.useTls = self.useTls
        self.xmlstream.namespace = self.namespace
        self.xmlstream.otherHost = self.otherHost
        self.xmlstream.otherEntity = jid.internJID(self.otherHost)
        self.xmlstream.prefixes = deepcopy(XMPP_PREFIXES)
        self.xmlstream.sendHeader()

    def streamStarted(self, rootelem=None):
        xmlstream.ConnectAuthenticator.streamStarted(self, rootelem)
        if rootelem is None:
            self.xversion = 3
            return

        self.xversion = 0
        if rootelem.hasAttribute('version'):
            self.version = rootelem['version']
        else:
            self.version = 0.0

    def associateWithStream(self, xs):
        xmlstream.ConnectAuthenticator.associateWithStream(self, xs)
        inits = [(xmlstream.TLSInitiatingInitializer, False)]

        for initClass, required in inits:
            init = initClass(xs)
            init.required = required
            xs.initializers.append(init)

    def _reset(self):
        # need this to be in xmlstream
        stream = domish.elementStream()
        stream.DocumentStartEvent = self.xmlstream.onDocumentStart
        stream.ElementEvent = self.xmlstream.onElement
        stream.DocumentEndEvent = self.xmlstream.onDocumentEnd
        self.xmlstream.stream = stream
        self.xmlstream.prefixes = deepcopy(XMPP_PREFIXES)
        # Generate stream header

        if self.version != 0.0:
            sh = ("<stream:stream xmlns='%s' "
                  "xmlns:stream='http://etherx.jabber.org/streams' "
                  "version='%s' to='%s'>") % (self.namespace,
                                              self.version,
                                              self.streamHost.encode('utf-8'))
            self.xmlstream.send(str(sh))

    def sendAuth(self, jid, passwd, callback, errback=None):
        self.jid = jid
        self.passwd = passwd
        if errback:
            self.xmlstream.addObserver(INVALID_USER_EVENT, errback)
            self.xmlstream.addObserver(AUTH_FAILED_EVENT, errback)
        if self.version != '1.0':
            iq = client.IQ(self.xmlstream, "get")
            iq.addElement(("jabber:iq:auth", "query"))
            iq.query.addElement("username", content=jid.user)
            iq.addCallback(callback)
            iq.send()

    def authQueryResultEvent(self, iq, callback):
        if iq["type"] == "result":
            # Construct auth request
            iq = client.IQ(self.xmlstream, "set")
            iq.addElement(("jabber:iq:auth", "query"))
            iq.query.addElement("username", content=self.jid.user)
            iq.query.addElement("resource", content=self.jid.resource)

            # Prefer digest over plaintext
            if client.DigestAuthQry.matches(iq):
                digest = xmlstream.hashPassword(self.xmlstream.sid,
                                                self.passwd)
                iq.query.addElement("digest", content=digest)
            else:
                iq.query.addElement("password", content=self.passwd)

            iq.addCallback(callback)
            iq.send()
        else:
            # Check for 401 -- Invalid user
            if iq.error["code"] == "401":
                self.xmlstream.dispatch(iq, INVALID_USER_EVENT)
            else:
                self.xmlstream.dispatch(iq, AUTH_FAILED_EVENT)
