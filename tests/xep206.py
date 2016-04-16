
import os
import sys
import time
from twisted.internet import defer, protocol, reactor
from twisted.python import log
from punjab.httpb import *
import test_basic

from punjab import session

class DummyClient:
    """
    a client for testing
    """

class DummyTransport:
    """
    a transport for testing
    """

    def loseConnection(self):
        return None


class DummyXmlStream(object):
    """
    An xmlstream for testing
    """

    def __init__(self):
        self.elements = []
        self.transport = DummyTransport()

    def send(self, element):
        self.elements.append(element)


class DummyPint(object):
    """
    A `pint` input for testing
    """

    def __init__(self):
        self.v = False


class XEP0206TestCase(test_basic.TestCase):
    """
    Tests for Punjab compatability with http://www.xmpp.org/extensions/xep-0206.html
    """

    def testCreateSession(self):

        def _testSessionCreate(res):
            self.failUnless(res[0].localPrefixes['xmpp'] == NS_XMPP, 'xmpp namespace not defined')
            self.failUnless(res[0].localPrefixes['stream'] == NS_FEATURES, 'stream namespace not defined')
            self.failUnless(res[0].hasAttribute((NS_XMPP, 'version')), 'version not found')

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
        return d


class DeliveryFailureTestCase(XEP0206TestCase):
    """
    Tests for the XEP0206 message delivery failure NACK feature.
    """

    def setUp(self):
        XEP0206TestCase.setUp(self)
        self.xmlstream = DummyXmlStream()
        self.session = session.Session(
            DummyPint(),
            {
                'rid': 0,
                'to': '',
                'route': 'xmpp:127.0.0.1:8080',
            },  # Dummy values to satisfy the constructor. Not needed in tests.
        )
        self.session.xmlstream = self.xmlstream

    def tearDown(self):
        del self.session
        XEP0206TestCase.tearDown(self)

    def test_skips_presence(self):
        """
        Test that the NACK skips presence elements.
        """
        sentinel = domish.Element((None, 'presence'))
        self.session.elems.append(sentinel)
        self.session.disconnect()
        self.assertTrue(sentinel not in self.xmlstream.elements)

    def test_sends_messages(self):
        """
        Test that the NACK sends message elements.
        """
        sentinel = domish.Element((None, 'message'))
        self.session.elems.append(sentinel)
        self.session.disconnect()
        self.assertTrue(sentinel in self.xmlstream.elements)

    def test_sends_iq(self):
        """
        Test that the NACK sends iq elements.
        """
        sentinel = domish.Element((None, 'iq'))
        self.session.elems.append(sentinel)
        self.session.disconnect()
        self.assertTrue(sentinel in self.xmlstream.elements)

    def test_errors_dont_bubble_up(self):
        """
        Test that NACK failures don't tank the service
        """
        def fail(*args, **kwargs):
            raise Exception("You shouldn't see this.")
        self.session._handle_missed_messages = fail
        self.session.disconnect()
