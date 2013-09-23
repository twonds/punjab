from twisted.internet import defer, reactor, task
from twisted.words.xish import xpath

from twisted.python import log

from punjab import httpb_client

import test_basic


class XEP0124TestCase(test_basic.TestCase):
    """
    Tests for Punjab compatability with http://www.xmpp.org/extensions/xep-0124.html
    """


    def testCreateSession(self):
        """
        Test Section 7.1 of BOSH xep : http://www.xmpp.org/extensions/xep-0124.html#session
        """

        def _testSessionCreate(res):
            self.failUnless(res[0].name=='body', 'Wrong element')
            self.failUnless(res[0].hasAttribute('sid'), 'Not session id')

        def _error(e):
            # This fails on DNS
            log.err(e)

        BOSH_XML = """<body content='text/xml; charset=utf-8'
      hold='1'
      rid='1573741820'
      to='localhost'
      route='xmpp:127.0.0.1:%(server_port)i'
      secure='true'
      ver='1.6'
      wait='60'
      ack='1'
      xml:lang='en'
      xmlns='http://jabber.org/protocol/httpbind'/>
 """% { "server_port": self.server_port }

        d = self.proxy.connect(BOSH_XML).addCallback(_testSessionCreate)
        d.addErrback(_error)
        return d


    def testWhiteList(self):
        """
        Basic tests for whitelisting domains.
        """

        def _testSessionCreate(res):
            self.failUnless(res[0].name=='body', 'Wrong element')
            self.failUnless(res[0].hasAttribute('sid'), 'Not session id')

        def _error(e):
            # This fails on DNS
            log.err(e)

        self.hbs.white_list = ['.localhost']
        BOSH_XML = """<body content='text/xml; charset=utf-8'
      hold='1'
      rid='1573741820'
      to='localhost'
      route='xmpp:127.0.0.1:%(server_port)i'
      secure='true'
      ver='1.6'
      wait='60'
      ack='1'
      xml:lang='en'
      xmlns='http://jabber.org/protocol/httpbind'/>
 """% { "server_port": self.server_port }

        d = self.proxy.connect(BOSH_XML).addCallback(_testSessionCreate)
        d.addErrback(_error)
        return d

    def testWhiteListError(self):
        """
        Basic tests for whitelisting domains.
        """

        def _testSessionCreate(res):
            self.fail("Session should not be created")

        def _error(e):
            # This is the error we expect.
            if isinstance(e.value, ValueError) and e.value.args == ('400', 'Bad Request'):
                return True

            # Any other error, including the error raised from _testSessionCreate, should
            # be propagated up to the test runner.
            return e

        self.hbs.white_list = ['test']
        BOSH_XML = """<body content='text/xml; charset=utf-8'
      hold='1'
      rid='1573741820'
      to='localhost'
      route='xmpp:127.0.0.1:%(server_port)i'
      secure='true'
      ver='1.6'
      wait='60'
      ack='1'
      xml:lang='en'
      xmlns='http://jabber.org/protocol/httpbind'/>
 """% { "server_port": self.server_port }

        d = self.proxy.connect(BOSH_XML).addCallback(_testSessionCreate)
        d.addErrback(_error)
        return d

    def testSessionTimeout(self):
        """Test if we timeout correctly
        """

        def testTimeout(res):
            self.failUnlessEqual(res.value[0], '404')

        def testCBTimeout(res):
            # check for terminate if we expire
            terminate = res[0].getAttribute('type',False)
            self.failUnlessEqual(terminate, 'terminate')

        def sendTest():
            sd = self.send()
            sd.addCallback(testCBTimeout)
            sd.addErrback(testTimeout)
            return sd

        def testResend(res):
            self.failUnless(res[0].name=='body', 'Wrong element')
            s = self.b.service.sessions[self.sid]
            self.failUnless(s.inactivity==2,'Wrong inactivity value')
            self.failUnless(s.wait==2, 'Wrong wait value')
            return task.deferLater(reactor, s.wait+s.inactivity+1, sendTest)

        def testSessionCreate(res):
            self.failUnless(res[0].name=='body', 'Wrong element')
            self.failUnless(res[0].hasAttribute('sid'),'Not session id')
            self.sid = res[0]['sid']

            # send and wait
            sd = self.send()
            sd.addCallback(testResend)
            return sd



        BOSH_XML = """<body content='text/xml; charset=utf-8'
      hold='1'
      rid='%(rid)i'
      to='localhost'
      route='xmpp:127.0.0.1:%(server_port)i'
      ver='1.6'
      wait='2'
      ack='1'
      inactivity='2'
      xml:lang='en'
      xmlns='http://jabber.org/protocol/httpbind'/>
 """% { "rid": self.rid, "server_port": self.server_port }

        return self.proxy.connect(BOSH_XML).addCallbacks(testSessionCreate)

    def testRemoteError(self):
        """
        This is to test if we get errors when there are no waiting requests.
        """

        def _testStreamError(res):
            self.assertEqual(True, isinstance(res.value, httpb_client.HTTPBNetworkTerminated))

            self.assertEqual(True, res.value.body_tag.hasAttribute('condition'), 'No attribute condition')
            # This is not a stream error because we sent invalid xml
            self.assertEqual(res.value.body_tag['condition'], 'remote-stream-error')
            self.assertEqual(True, len(res.value.elements)>0)
            # The XML should exactly match the error XML sent by triggerStreamError().
            self.assertEqual(True,xpath.XPathQuery("/error").matches(res.value.elements[0]))
            self.assertEqual(True,xpath.XPathQuery("/error/policy-violation").matches(res.value.elements[0]))
            self.assertEqual(True,xpath.XPathQuery("/error/arbitrary-extension").matches(res.value.elements[0]))
            self.assertEqual(True,xpath.XPathQuery("/error/text[text() = 'Error text']").matches(res.value.elements[0]))



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
      rid='%(rid)i'
      to='localhost'
      route='xmpp:127.0.0.1:%(server_port)i'
      ver='1.6'
      wait='60'
      ack='1'
      xml:lang='en'
      xmlns='http://jabber.org/protocol/httpbind'/>
 """% { "rid": self.rid, "server_port": self.server_port }

        d = self.proxy.connect(BOSH_XML).addCallback(_testSessionCreate)

        return d


    @defer.inlineCallbacks
    def testStreamFlushOnError(self):
        """
        Test that messages included in a <body type='terminate'> message from the
        client are sent to the server before terminating.
        """
        yield self.connect(self.get_body_node(connect=True))

        # Set got_testing_node to true when the XMPP server receives the <testing/> we
        # send below.
        got_testing_node = [False] # work around Python's 2.6 lack of nonlocal
        wait = defer.Deferred()
        def received_testing(a):
            got_testing_node[0] = True
            wait.callback(True)
        self.server_protocol.addObserver("/testing", received_testing)

        # Ensure that we always remove the received_testing listener.
        try:
            # Send <body type='terminate'><testing/></body>.  This should result in a
            # HTTPBNetworkTerminated exception.
            try:
                yield self.proxy.send(self.get_body_node(ext='<testing/>', type='terminate'))
            except httpb_client.HTTPBNetworkTerminated as e:
                self.failUnlessEqual(e.body_tag.getAttribute('condition', None), None)

            # Wait until <testing/> is actually received by the XMPP server.  The previous
            # request completing only means that the proxy has received the stanza, not that
            # it's been delivered to the XMPP server.
            yield wait

        finally:
            self.server_protocol.removeObserver("/testing", received_testing)

        # This should always be true, or we'd never have woken up from wait.
        self.assertEqual(True,got_testing_node[0])

    @defer.inlineCallbacks
    def testTerminateRace(self):
        """Test that buffered messages are flushed when the connection is terminated."""
        yield self.connect(self.get_body_node(connect=True))

        def log_observer(event):
            self.failIf(event['isError'], event)

        log.addObserver(log_observer)

        # Simultaneously cause a stream error (server->client closed) and send a terminate
        # from the client to the server.  Both sides are closing the connection at once.
        # Make sure the connection closes cleanly without logging any errors ("Unhandled
        # Error"), and the client receives a terminate in response.
        try:
            self.server_protocol.triggerStreamError()
            yield self.proxy.send(self.get_body_node(type='terminate'))
        except httpb_client.HTTPBNetworkTerminated as e:
            self.assertEqual(e.body_tag.getAttribute('condition', None), 'remote-stream-error')
        finally:
            log.removeObserver(log_observer)

    @defer.inlineCallbacks
    def testStreamKeying1(self):
        """Test that connections succeed when stream keying is active."""

        yield self.connect(self.get_body_node(connect=True, useKey=True))
        yield self.proxy.send(self.get_body_node(useKey=True))
        yield self.proxy.send(self.get_body_node(useKey=True))

    @defer.inlineCallbacks
    def testStreamKeying2(self):
        """Test that 404 is received if stream keying is active and no key is supplied."""
        yield self.connect(self.get_body_node(connect=True, useKey=True))

        try:
            yield self.proxy.send(self.get_body_node(useKey=False))
        except httpb_client.HTTPBNetworkTerminated as e:
            self.failUnlessEqual(e.body_tag.getAttribute('condition', None), 'item-not-found')
        else:
            self.fail("Expected 404 Not Found")


    @defer.inlineCallbacks
    def testStreamKeying3(self):
        """Test that 404 is received if stream keying is active and an invalid key is supplied."""
        yield self.connect(self.get_body_node(connect=True, useKey=True))

        try:
            yield self.proxy.send(self.get_body_node(useKey=True, key='0'*40))
        except httpb_client.HTTPBNetworkTerminated as e:
            self.failUnlessEqual(e.body_tag.getAttribute('condition', None), 'item-not-found')
        else:
            self.fail("Expected 404 Not Found")


    @defer.inlineCallbacks
    def testStreamKeying4(self):
        """Test that 404 is received if we supply a key on a connection without active keying."""
        yield self.connect(self.get_body_node(connect=True, useKey=False))

        try:
            yield self.proxy.send(self.get_body_node(key='0'*40))
        except httpb_client.HTTPBNetworkTerminated as e:
            self.failUnlessEqual(e.body_tag.getAttribute('condition', None), 'item-not-found')
        else:
            self.fail("Expected 404 Not Found")

    @defer.inlineCallbacks
    def testStreamKeying5(self):
        """Test rekeying."""
        yield self.connect(self.get_body_node(connect=True, useKey=True))
        yield self.proxy.send(self.get_body_node(useKey=True))

        # Erase all but the last key to force a rekeying.
        self.keys.k = [self.keys.k[-1]]

        yield self.proxy.send(self.get_body_node(useKey=True))
        yield self.proxy.send(self.get_body_node(useKey=True))


    def testStreamParseError(self):
        """
        Test that remote-connection-failed is received when the proxy receives invalid XML
        from the XMPP server.
        """

        def _testStreamError(res):
            self.assertEqual(True, isinstance(res.value, httpb_client.HTTPBNetworkTerminated))
            self.assertEqual(res.value.body_tag.getAttribute('condition', None), 'remote-connection-failed')

        def _failStreamError(res):
            self.fail('Expected a remote-connection-failed error')

        def _testSessionCreate(res):
            self.sid = res[0]['sid']
            self.server_protocol.triggerInvalidXML()
            return self.send().addCallbacks(_failStreamError, _testStreamError)

        return self.proxy.connect(self.get_body_node(connect=True)).addCallback(_testSessionCreate)

    def testFeaturesError(self):
        """
        This is to test if we get stream features and NOT twice
        """

        def _testError(res):
            self.assertEqual(True,res[1][0].name=='challenge','Did not get correct challenge stanza')

        def _testSessionCreate(res):
            self.sid = res[0]['sid']
            # this xml is valid, just for testing
            # the point is to wait for a stream error
            self.assertEqual(True,res[1][0].name=='features','Did not get initial features')

            d = self.send("<auth xmlns='urn:ietf:params:xml:ns:xmpp-sasl' mechanism='DIGEST-MD5'/>")
            d.addCallback(_testError)
            reactor.callLater(1.1, self.server_protocol.triggerChallenge)
            return d

        BOSH_XML = """<body content='text/xml; charset=utf-8'
      hold='1'
      rid='%(rid)i'
      to='localhost'
      route='xmpp:127.0.0.1:%(server_port)i'
      ver='1.6'
      wait='15'
      ack='1'
      xml:lang='en'
      xmlns='http://jabber.org/protocol/httpbind'/>
 """% { "rid": self.rid, "server_port": self.server_port }
        self.server_factory.protocol.delay_features = 3

        d = self.proxy.connect(BOSH_XML).addCallback(_testSessionCreate)
        # NOTE : to trigger this bug there needs to be 0 waiting requests.

        return d


    def testRidCountBug(self):
        """
        This is to test if rid becomes off on resends
        """
        @defer.inlineCallbacks
        def _testError(res):
            self.assertEqual(res[1][0].name, 'challenge','Did not get correct challenge stanza')
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
            self.assertEqual(res[1][0].name, 'features','Did not get initial features')

            d = self.send("<auth xmlns='urn:ietf:params:xml:ns:xmpp-sasl' mechanism='DIGEST-MD5'/>")
            d.addCallback(_testError)
            reactor.callLater(1, self.server_protocol.triggerChallenge)

            return d

        BOSH_XML = """<body content='text/xml; charset=utf-8'
      hold='1'
      rid='%(rid)i'
      to='localhost'
      route='xmpp:127.0.0.1:%(server_port)i'
      ver='1.6'
      wait='3'
      ack='1'
      xml:lang='en'
      xmlns='http://jabber.org/protocol/httpbind'/>
 """% { "rid": self.rid, "server_port": self.server_port }

        self.server_factory.protocol.delay_features = 10
        d = self.proxy.connect(BOSH_XML).addCallback(_testSessionCreate)
        # NOTE : to trigger this bug there needs to be 0 waiting requests.

        return d


