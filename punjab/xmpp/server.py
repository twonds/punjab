# XMPP server class

from twisted.application import service
from twisted.python import components

from twisted.internet import reactor


from twisted.words.xish import domish, xpath, xmlstream
from twisted.words.protocols.jabber import jid

from punjab.xmpp import ns

SASL_XMLNS = 'urn:ietf:params:xml:ns:xmpp-sasl'
COMP_XMLNS = 'http://jabberd.jabberstudio.org/ns/component/1.0'
STREAMS_XMLNS  = 'urn:ietf:params:xml:ns:xmpp-streams'

from zope.interface import Interface, implements

# interfaces
class IXMPPServerService(Interface):
    pass

class IXMPPServerFactory(Interface):
    pass

class IXMPPFeature(Interface):
    pass

class IXMPPAuthenticationFeature(IXMPPFeature):
    pass

class IQAuthFeature(object):
    """ XEP-0078 : http://www.xmpp.org/extensions/xep-0078.html"""

    implements(IXMPPAuthenticationFeature)


    IQ_GET_AUTH = xpath.internQuery(ns.IQ_GET_AUTH)
    IQ_SET_AUTH = xpath.internQuery(ns.IQ_SET_AUTH)


    def associateWithStream(self, xs):
        """Add a streamm start event observer.
           And do other things to associate with the xmlstream if necessary.
        """
        self.xmlstream = xs
        self.xmlstream.addOnetimeObserver(xmlstream.STREAM_START_EVENT,
                                          self.streamStarted)

    def disassociateWithStream(self, xs):
        self.xmlstream.removeObserver(self.IQ_GET_AUTH,
                                      self.authRequested)
        self.xmlstream.removeObserver(self.IQ_SET_AUTH,
                                      self.auth)
        self.xmlstream = None


    def streamStarted(self, elm):
        """
        Called when client sends stream:stream
        """
        self.xmlstream.addObserver(self.IQ_GET_AUTH,
                                   self.authRequested)
        self.xmlstream.addObserver(self.IQ_SET_AUTH,
                                   self.auth)

    def authRequested(self, elem):
        """Return the supported auth type.

        """
        resp = domish.Element(('iq', ns.NS_CLIENT))
        resp['type'] = 'result'
        resp['id'] = elem['id']
        q = resp.addElement("query", ns.NS_AUTH)
        q.addElement("username", content=str(elem.query.username))
        q.addElement("digest")
        q.addElement("password")
        q.addElement("resource")

        self.xmlstream.send(resp)

    def auth(self, elem):
        """Do not auth the user, anyone can log in"""

        username = elem.query.username.__str__()
        resource = elem.query.resource.__str__()

        user = jid.internJID(username+'@'+self.xmlstream.host+'/'+resource)

        resp = domish.Element(('iq', ns.NS_CLIENT))
        resp['type'] = 'result'
        resp['id'] = elem['id']

        self.xmlstream.send(resp)

        self.xmlstream.authenticated(user)



class XMPPServerProtocol(xmlstream.XmlStream):
    """ Basic dummy server protocol """
    host = "localhost"
    user = None
    initialized = False
    id = 'Punjab123'
    features = [IQAuthFeature()]
    delay_features = 0

    def connectionMade(self):
        """
        a client connection has been made
        """
        xmlstream.XmlStream.connectionMade(self)

        self.bootstraps = [
            (xmlstream.STREAM_CONNECTED_EVENT, self.streamConnected),
            (xmlstream.STREAM_START_EVENT, self.streamStarted),
            (xmlstream.STREAM_END_EVENT, self.streamEnded),
            (xmlstream.STREAM_ERROR_EVENT, self.streamErrored),
            ]

        for event, fn in self.bootstraps:
            self.addObserver(event, fn)

        # load up the authentication features
        for f in self.features:
            if IXMPPAuthenticationFeature.implementedBy(f.__class__):
                f.associateWithStream(self)

    def send(self, obj):
        if not self.initialized:
            self.transport.write("""<?xml version="1.0"?>\n""")
            self.initialized = True
        xmlstream.XmlStream.send(self, obj)


    def streamConnected(self, elm):
        print "stream connected"

    def streamStarted(self, elm):
        """stream has started, we need to respond

        """
        if self.delay_features == 0:
            self.send("""<stream:stream xmlns='%s' xmlns:stream='http://etherx.jabber.org/streams' from='%s' id='%s' version='1.0' xml:lang='en'><stream:features><register xmlns='http://jabber.org/features/iq-register'/></stream:features>""" % (ns.NS_CLIENT, self.host, self.id,))
        else:
            self.send("""<stream:stream xmlns='%s' xmlns:stream='http://etherx.jabber.org/streams' from='%s' id='%s' version='1.0' xml:lang='en'>""" % (ns.NS_CLIENT, self.host, self.id,))
            reactor.callLater(self.delay_features, self.send, """<stream:features><register xmlns='http://jabber.org/features/iq-register'/></stream:features>""")

    def streamEnded(self, elm):
        self.send("""</stream:stream>""")

    def streamErrored(self, elm):
        self.send("""<stream:error/></stream:stream>""")

    def authenticated(self, user):
        """User has authenticated.
        """
        self.user = user

    def onElement(self, element):
        try:
            xmlstream.XmlStream.onElement(self, element)
        except Exception, e:
            print "Exception!", e
            raise e

    def onDocumentEnd(self):
        pass

    def connectionLost(self, reason):
        xmlstream.XmlStream.connectionLost(self, reason)
        pass

    def triggerChallenge(self):
        """ send a fake challenge for testing
        """
        self.send("""<challenge xmlns='urn:ietf:params:xml:ns:xmpp-sasl'>cmVhbG09ImNoZXNzcGFyay5jb20iLG5vbmNlPSJ0YUhIM0FHQkpQSE40eXNvNEt5cFlBPT0iLHFvcD0iYXV0aCxhdXRoLWludCIsY2hhcnNldD11dGYtOCxhbGdvcml0aG09bWQ1LXNlc3M=</challenge>""")


    def triggerInvalidXML(self):
        """Send invalid XML, to trigger a parse error."""
        self.send("""<parse error=>""")
        self.streamEnded(None)

    def triggerStreamError(self):
        """ send a stream error
        """
        self.send("""
        <stream:error xmlns:stream='http://etherx.jabber.org/streams'>
            <policy-violation xmlns='urn:ietf:params:xml:ns:xmpp-streams'/>
            <text xmlns='urn:ietf:params:xml:ns:xmpp-streams' xml:lang='langcode'>Error text</text>
            <arbitrary-extension val='2'/>
        </stream:error>""")
        self.streamEnded(None)



class XMPPServerFactoryFromService(xmlstream.XmlStreamFactory):
    implements(IXMPPServerFactory)

    protocol = XMPPServerProtocol

    def __init__(self, service):
        xmlstream.XmlStreamFactory.__init__(self)
        self.service = service


    def buildProtocol(self, addr):
        self.resetDelay()
        xs = self.protocol()
        xs.factory = self
        for event, fn in self.bootstraps:
            xs.addObserver(event, fn)
        return xs


components.registerAdapter(XMPPServerFactoryFromService,
                           IXMPPServerService,
                           IXMPPServerFactory)


class XMPPServerService(service.Service):

    implements(IXMPPServerService)



