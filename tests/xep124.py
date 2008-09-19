
import os
import sys, sha, random
from twisted.trial import unittest
import time
from twisted.web import server, resource, static, http, client
from twisted.words.protocols.jabber import jid
from twisted.internet import defer, protocol, reactor
from twisted.application import internet, service
from twisted.words.xish import domish, xpath

from twisted.python import log

from punjab.httpb import HttpbService
from punjab.xmpp import server as xmppserver
import httpb_client

class DummyTransport:
    
    def __init__(self):
        self.data = []
 	       
    def write(self, bytes):
        self.data.append(bytes)
 	
    def loseConnection(self, *args, **kwargs):
        self.data = []

class XEP0124TestCase(unittest.TestCase):
    """
    Tests for Punjab compatability with http://www.xmpp.org/extensions/xep-0124.html
    """

    def setUp(self):
        # set up punjab
        os.mkdir("./html") # create directory in _trial_temp
        self.root = static.File("./html") # make _trial_temp/html the root html directory
        self.rid = random.randint(0,10000000)
        self.b = resource.IResource(HttpbService(1))
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
        self.server = reactor.listenTCP(5222, self.server_factory, interface="127.0.0.1")

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
        if self.keys.lastKey():
            self.keys.setKeys()
        
        if self.keys.firstKey():
            b['newkey'] = self.keys.getKey()
        else:
            b['key'] = self.keys.getKey()
        return b 

    def resend(self, ext = None):
        self.rid = self.rid - 1
        return self.send(ext)

    def send(self, ext = None):
        b = domish.Element(("http://jabber.org/protocol/httpbind","body"))
        b['content']  = 'text/xml; charset=utf-8'
        self.rid = self.rid + 1
        b['rid']      = str(self.rid)
        b['sid']      = str(self.sid)
        b['xml:lang'] = 'en'
        
        if ext is not None:
            if isinstance(ext, domish.Element):
                b.addChild(ext)
            else:
                b.addRawXml(ext)

        b = self.key(b)
        
        d = self.proxy.send(b)
        return d

    def testCreateSession(self):
        """
        Test Section 7.1 of BOSH xep : http://www.xmpp.org/extensions/xep-0124.html#session
        """
        
        def _testSessionCreate(res):
            self.failUnless(res[0].name=='body', 'Wrong element')
            
            self.failUnless(res[0].hasAttribute('sid'),'Not session id')
            

        BOSH_XML = """<body content='text/xml; charset=utf-8'
      hold='1'
      rid='1573741820'
      to='jabber.org'
      secure='true'
      ver='1.6'
      wait='60'
      ack='1'
      xml:lang='en'
      xmlns='http://jabber.org/protocol/httpbind'/>
 """

        d = self.proxy.connect(BOSH_XML).addCallback(_testSessionCreate)

        return d


    def testSessionTimeout(self):
        """Test if we timeout correctly
        """
        d = defer.Deferred()

        def testTimeout(res):
            passed = True
            
            if res.value[0]!='404':
                passed = False
                d.errback((Exception, 'Wrong Value %s '% (str(res.value),)))
            if passed:
                d.callback(True)
            else:
                log.err(res)

        def testCBTimeout(res):
            # check for terminate if we expire 
            terminate = res[0].getAttribute('type',False)
            
            if str(terminate) != 'terminate':
                d.errback((Exception, 'Was not terminate'))
                return
            d.callback(True)

        def sendTest():
            sd = self.send()
            sd.addCallback(testCBTimeout)
            sd.addErrback(testTimeout)
            

        def testResend(res):
            self.failUnless(res[0].name=='body', 'Wrong element')
            s = self.b.service.sessions[self.sid]
            self.failUnless(s.inactivity==10,'Wrong inactivity value')
            self.failUnless(s.wait==10, 'Wrong wait value')
            reactor.callLater(s.wait+s.inactivity+1, sendTest)
            

        def testSessionCreate(res):
            self.failUnless(res[0].name=='body', 'Wrong element')            
            self.failUnless(res[0].hasAttribute('sid'),'Not session id')
            self.sid = res[0]['sid']

            # send and wait 
            sd = self.send()
            
            sd.addCallback(testResend)
            


        BOSH_XML = """<body content='text/xml; charset=utf-8'
      hold='1'
      rid='%d'
      to='localhost'
      route='xmpp:127.0.0.1:5222'
      ver='1.6'
      wait='10'
      ack='1'
      inactivity='10'
      xml:lang='en'
      xmlns='http://jabber.org/protocol/httpbind'/>
 """% (self.rid,)

        self.proxy.connect(BOSH_XML).addCallback(testSessionCreate)
        d.addErrback(self.fail)
        return d

    def testStreamError(self):
        """
        This is to test if we get stream errors when there are no waiting requests.
        """
        
        def _testStreamError(res):
            self.failUnless(res.value[0].hasAttribute('condition'), 'No attribute condition')
            self.failUnless(res.value[0]['condition'] == 'remote-stream-error', 'Condition should be remote stream error')
            self.failUnless(res.value[1][0].children[0].name == 'policy-violation', 'Error should be policy violation')



        def _failStreamError(res):
            self.fail('A stream error needs to be returned')
            
        def _testSessionCreate(res):
            self.sid = res[0]['sid']
            # this xml is valid, just for testing
            # the point is to wait for a stream error
            d = self.send('<fdsfd/>')
            d.addCallback(_failStreamError)
            d.addErrback(_testStreamError)
            self.server_protocol.triggerStreamError()

            return d
            
        BOSH_XML = """<body content='text/xml; charset=utf-8'
      hold='1'
      rid='%d'
      to='localhost'
      route='xmpp:127.0.0.1:5222'
      ver='1.6'
      wait='60'
      ack='1'
      xml:lang='en'
      xmlns='http://jabber.org/protocol/httpbind'/>
 """ % (self.rid,)

        d = self.proxy.connect(BOSH_XML).addCallback(_testSessionCreate)

        return d



    def testFeaturesError(self):
        """
        This is to test if we get stream features and NOT twice
        """
        
        def _testError(res):
            self.failUnless(res[1][0].name=='challenge','Did not get correct challenge stanza')

        def _testSessionCreate(res):
            self.sid = res[0]['sid']
            # this xml is valid, just for testing
            # the point is to wait for a stream error
            self.failUnless(res[1][0].name=='features','Did not get initial features')
            
            # self.send("<auth xmlns='urn:ietf:params:xml:ns:xmpp-sasl' mechanism='DIGEST-MD5'/>")
            d = self.send("<auth xmlns='urn:ietf:params:xml:ns:xmpp-sasl' mechanism='DIGEST-MD5'/>")
            d.addCallback(_testError)
            reactor.callLater(1, self.server_protocol.triggerChallenge)

            return d
            
        BOSH_XML = """<body content='text/xml; charset=utf-8'
      hold='1'
      rid='%d'
      to='localhost'
      route='xmpp:127.0.0.1:5222'
      ver='1.6'
      wait='3'
      ack='1'
      xml:lang='en'
      xmlns='http://jabber.org/protocol/httpbind'/>
 """ % (self.rid,)

        self.server_factory.protocol.delay_features = 10

        d = self.proxy.connect(BOSH_XML).addCallback(_testSessionCreate)
        # NOTE : to trigger this bug there needs to be 0 waiting requests.
        
        return d


    def testRidCountBug(self):
        """
        This is to test if rid becomes off on resends
        """
        @defer.inlineCallbacks
        def _testError(res):
            self.failUnless(res[1][0].name=='challenge','Did not get correct challenge stanza')
            for r in range(5):
                # send auth to bump up rid
                res = yield self.send("<auth xmlns='urn:ietf:params:xml:ns:xmpp-sasl' mechanism='DIGEST-MD5'/>")
            # resend auth
            for r in range(5):
                res = yield self.resend("<auth xmlns='urn:ietf:params:xml:ns:xmpp-sasl' mechanism='DIGEST-MD5'/>")
            
            res = yield self.resend("<auth xmlns='urn:ietf:params:xml:ns:xmpp-sasl' mechanism='DIGEST-MD5'/>")
                

        def _testSessionCreate(res):
            self.sid = res[0]['sid']
            # this xml is valid, just for testing
            # the point is to wait for a stream error
            self.failUnless(res[1][0].name=='features','Did not get initial features')
            
            # self.send("<auth xmlns='urn:ietf:params:xml:ns:xmpp-sasl' mechanism='DIGEST-MD5'/>")
            d = self.send("<auth xmlns='urn:ietf:params:xml:ns:xmpp-sasl' mechanism='DIGEST-MD5'/>")
            d.addCallback(_testError)
            reactor.callLater(1, self.server_protocol.triggerChallenge)

            return d
            
        BOSH_XML = """<body content='text/xml; charset=utf-8'
      hold='1'
      rid='%d'
      to='localhost'
      route='xmpp:127.0.0.1:5222'
      ver='1.6'
      wait='3'
      ack='1'
      xml:lang='en'
      xmlns='http://jabber.org/protocol/httpbind'/>
 """ % (self.rid,)

        self.server_factory.protocol.delay_features = 10

        d = self.proxy.connect(BOSH_XML).addCallback(_testSessionCreate)
        # NOTE : to trigger this bug there needs to be 0 waiting requests.
        
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
        removedSelectables = reactor.removeAll()
        # Below is commented out to remind us how to see what selectable is sticking around
        #if removedSelectables:
        #    for sel in removedSelectables:
        #        # del sel
        #        print sel.__class__
        #        print dir(sel)
        
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
            self.b.service.endSession(self.b.service.sessions[s])
        if hasattr(self.proxy.factory,'client'):
            self.proxy.factory.client.transport.stopConnecting()
        

        d = defer.maybeDeferred(self.server.stopListening)
        d.addCallback(cbStopListening)

        return d
        
