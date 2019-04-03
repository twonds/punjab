# punjab's jabber client
from twisted.internet import reactor, error
from twisted.words.protocols.jabber import client, jid
from twisted.python import log
from copy import deepcopy

from twisted.words.xish.domish import ExpatElementStream, SuxElementStream
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
        log.msg("RECV: %s" % buf.decode('utf-8'))

    def rawDataOut(self, buf):
        log.msg("SEND: %s" % buf.decode('utf-8'))


class ShallowExpatElementStream(ExpatElementStream):
    """Modification of parser that doesn't build xml tree for stanza payload.

    Make stream parser handle only top level stanza tags. In this way payload
    (all xml elements with depth > 1) will not be parsed into xml tree. This
    optimization would particularly be useful for <iq> stanzas, as they may
    contain large payload (e.g. roster)

    """
    STANZA_TYPES = ['message', 'presence', 'iq']

    def __init__(self, *args, **kwargs):
        ExpatElementStream.__init__(self, *args, **kwargs)
        self._depth = 0
        self._cur_stanza = None

    def _parse_tag_name(self, name):
        qname = name.split(' ')
        # Namespace is not present
        if len(qname) == 1:
            tag_name = qname[0]
        # Take only tag name
        elif len(qname) == 2:
            tag_name = qname[1]
        else:
            tag_name = None

        return tag_name

    def _onStartElement(self, name, attrs):
        self._depth += 1
        if self._cur_stanza is None:
            tag_name = self._parse_tag_name(name)
            if tag_name in self.STANZA_TYPES:
                self._cur_stanza = (tag_name, self._depth)
            ExpatElementStream._onStartElement(self, name, attrs)
        else:
            return

    def _onEndElement(self, name):
        if self._cur_stanza is not None:
            if self._depth == self._cur_stanza[1]:
                self._depth -= 1
                self._cur_stanza = None
                ExpatElementStream._onEndElement(self, name)
            else:
                self._depth -= 1
                return
        else:
            self._depth -= 1
            ExpatElementStream._onEndElement(self, name)


def elementStream(shallow=False):
    """ Preferred method to construct an ElementStream

    Uses regular or 'shallow' Expat-based stream if available,
    and falls back to Sux if necessary.

    """
    try:
        if shallow:
            es = ShallowExpatElementStream()
        else:
            es = ExpatElementStream()
        return es
    except ImportError:
        if SuxElementStream is None:
            raise Exception("No parsers available :(")
        es = SuxElementStream()
        return es


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

    def _reset(self, shallow=False):
        # need this to be in xmlstream
        stream = elementStream(shallow)
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
                                              self.streamHost)
            self.xmlstream.send(sh)

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
