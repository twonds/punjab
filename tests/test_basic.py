
import os
import os.path
import random
from twisted.trial import unittest

from twisted.web import server, resource, static

from twisted.internet import defer, reactor

from twisted.words.xish import domish

from punjab.httpb import HttpbService
from punjab.xmpp import server as xmppserver
from punjab import httpb_client

class DummyTransport:

    def __init__(self):
        self.data = []

    def write(self, bytes):
        self.data.append(bytes)

    def loseConnection(self, *args, **kwargs):
        self.data = []

class TestCase(unittest.TestCase):
    """Basic test class for Punjab
    """

    def setUp(self):
        # set up punjab
        html_dir = "./html"
        if not os.path.exists(html_dir):
            os.mkdir(html_dir) # create directory in _trial_temp
        self.root = static.File(html_dir) # make _trial_temp/html the root html directory
        self.rid = random.randint(0,10000000)
        self.hbs = HttpbService(1)
        self.b = resource.IResource(self.hbs)
        self.root.putChild('xmpp-bosh', self.b)

        self.site  = server.Site(self.root)

        self.p =  reactor.listenTCP(0, self.site, interface="127.0.0.1")
        self.port = self.p.getHost().port

        # set up proxy

        self.proxy = httpb_client.Proxy(self.getURL())
        self.sid   = None
        self.keys  = httpb_client.Keys()

        # set up dummy xmpp server

        self.server_service = xmppserver.XMPPServerService()
        self.server_factory = xmppserver.IXMPPServerFactory(self.server_service)
        self.server = reactor.listenTCP(0, self.server_factory, interface="127.0.0.1")
        self.server_port = self.server.socket.getsockname()[1]

        # Hook the server's buildProtocol to make the protocol instance
        # accessible to tests.
        buildProtocol = self.server_factory.buildProtocol
        d1 = defer.Deferred()
        def _rememberProtocolInstance(addr):
            self.server_protocol = buildProtocol(addr)
            # keeping this around because we may want to wrap this specific to tests
            # self.server_protocol = protocol.wrappedProtocol
            d1.callback(None)
            return self.server_protocol
        self.server_factory.buildProtocol = _rememberProtocolInstance


    def getURL(self, path = "xmpp-bosh"):
        return "http://127.0.0.1:%d/%s" % (self.port, path)


    def key(self,b):
        key, newkey = self.keys.getKey()

        if key:
            b['key'] = key
        if newkey:
            b['newkey'] = newkey

        return b

    def resend(self, ext = None):
        self.rid = self.rid - 1
        return self.send(ext)

    def get_body_node(self, ext=None, sid=None, rid=None, useKey=False, connect=False, **kwargs):
        self.rid = self.rid + 1
        if sid is None:
            sid = self.sid
        if rid is None:
            rid = self.rid
        b = domish.Element(("http://jabber.org/protocol/httpbind","body"))
        b['content']  = 'text/xml; charset=utf-8'
        b['hold'] = '0'
        b['wait'] = '60'
        b['ack'] = '1'
        b['xml:lang'] = 'en'
        b['rid'] = str(rid)

        if sid:
            b['sid'] = str(sid)

        if connect:
            b['to'] = 'localhost'
            b['route'] = 'xmpp:127.0.0.1:%i' % self.server_port
            b['ver'] = '1.6'

        if useKey:
            self.key(b)

        if ext is not None:
            if isinstance(ext, domish.Element):
                b.addChild(ext)
            else:
                b.addRawXml(ext)

        for key, value in kwargs.iteritems():
            b[key] = value
        return b

    def send(self, ext = None, sid = None, rid = None):
        b = self.get_body_node(ext, sid, rid)
        d = self.proxy.send(b)
        return d

    def _storeSID(self, res):
        self.sid = res[0]['sid']
        return res

    def connect(self, b):
        d = self.proxy.connect(b)
        # If we don't already have a SID, store the one we get back.
        if not self.sid:
            d.addCallback(self._storeSID)
        return d


    def _error(self, e):
        # self.fail(e)
        pass

    def _cleanPending(self):
        pending = reactor.getDelayedCalls()
        if pending:
            for p in pending:
                if p.active():
                    p.cancel()

    def _cleanSelectables(self):
        reactor.removeAll()

    def tearDown(self):
        def cbStopListening(result=None):
            self.root = None
            self.site = None
            self.proxy.factory.stopFactory()
            self.server_factory.stopFactory()
            self.server = None
            self._cleanPending()
            self._cleanSelectables()

        os.rmdir("./html") # remove directory from _trial_temp
        self.b.service.poll_timeouts.stop()
        self.b.service.stopService()
        self.p.stopListening()
        for s in self.b.service.sessions.keys():
            sess = self.b.service.sessions.get(s)
            if sess:
                self.b.service.endSession(sess)
        if hasattr(self.proxy.factory,'client'):
            self.proxy.factory.client.transport.stopConnecting()
        self.server_factory.protocol.delay_features = 0

        d = defer.maybeDeferred(self.server.stopListening)
        d.addCallback(cbStopListening)

        return d

