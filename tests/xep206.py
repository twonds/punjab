
import os
import sys
import time
from twisted.internet import defer, protocol, reactor
from twisted.python import log
from punjab.httpb import *
import test_basic

class DummyClient:
    """
    a client for testing
    """

class DummyTransport:
    """
    a transport for testing
    """



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

