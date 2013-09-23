
import os
import sys
from twisted.trial import unittest
import time
from twisted.words.protocols.jabber import jid
from twisted.internet import defer, protocol, reactor
from twisted.application import internet, service
from twisted.words.xish import domish, xpath

from twisted.python import log

class DummyClient:
    """
    a client for testing
    """

class DummyTransport:
    """
    a transport for testing
    """



class XEP0206TestCase(unittest.TestCase):
    """
    Tests for Punjab compatability with http://www.xmpp.org/extensions/xep-0206.html
    """

