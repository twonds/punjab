
import os
import sys, random
from twisted.trial import unittest
import time
from twisted.web import server, resource, static, http, client
from twisted.words.protocols.jabber import jid
from twisted.internet import defer, protocol, reactor
from twisted.application import internet, service
from twisted.words.xish import domish, xpath

from twisted.python import log

from punjab.httpb import HttpbParse



class ParseTestCase(unittest.TestCase):
    """
    Tests for Punjab compatability with http://www.xmpp.org/extensions/xep-0124.html
    """

    def testTime(self):
        XML = """
 <body rid='4019888743' xmlns='http://jabber.org/protocol/httpbind' sid='948972a64d524f862107cdbd748d1d16'><iq id='980:getprefs' type='get'><query xmlns='jabber:iq:private'><preferences xmlns='http://chesspark.com/xml/chesspark-01'/></query></iq><iq id='981:getallignorelists' type='get'><query xmlns='jabber:iq:privacy'/></iq><test/><testing><ha/></testing></body>
"""
        t = time.time()

        for i in range(0, 10000):
            hp = HttpbParse(use_t=True)
            b, elems = hp.parse(XML)
            for e in elems:
                x = e.toXml()
        td = time.time() - t


        t = time.time()
        for i in range(0, 10000):
            hp = HttpbParse()
            b, elems = hp.parse(XML)
            for e in elems:
                if type(u'') == type(e):
                    x = e
                
        ntd = time.time() - t
        
        self.failUnless(td>ntd, 'Not faster')
        


    def testGtBug(self):
        XML = """ <body rid='1445008480' xmlns='http://jabber.org/protocol/httpbind' sid='1f2f8585f41e2dacf1f1f0ad83f8833d'><presence type='unavailable' from='KurodaJr@chesspark.com/cpc' to='5252844@games.chesspark.com/KurodaJr@chesspark.com'/><iq id='10059:enablepush' to='search.chesspark.com' type='set'><search xmlns='http://onlinegamegroup.com/xml/chesspark-01' node='play'><filter><relative-rating>500</relative-rating><time-control-range name='speed'/></filter></search></iq><iq id='10060:enablepush' to='search.chesspark.com' type='set'><search xmlns='http://onlinegamegroup.com/xml/chesspark-01' node='play'><filter><relative-rating>500</relative-rating><time-control-range name='speed'/></filter></search></iq></body>
"""
        hp = HttpbParse()

        b, e = hp.parse(XML)

        # need tests here
        self.failUnless(e[0]==u"<presence from='KurodaJr@chesspark.com/cpc' type='unavailable' to='5252844@games.chesspark.com/KurodaJr@chesspark.com'/>",'invalid xml')
        self.failUnless(e[1]==u"<iq to='search.chesspark.com' type='set' id='10059:enablepush'><search xmlns='http://onlinegamegroup.com/xml/chesspark-01' node='play'><filter><relative-rating>500</relative-rating><time-control-range name='speed'/></filter></search></iq>", 'invalid xml')
        self.failUnless(e[2]==u"<iq to='search.chesspark.com' type='set' id='10060:enablepush'><search xmlns='http://onlinegamegroup.com/xml/chesspark-01' node='play'><filter><relative-rating>500</relative-rating><time-control-range name='speed'/></filter></search></iq>", 'invalid xml')


    def testParse(self):
        XML = """
 <body rid='4019888743' xmlns='http://jabber.org/protocol/httpbind' sid='948972a64d524f862107cdbd748d1d16'><iq id='980:getprefs' type='get'><query xmlns='jabber:iq:private'><preferences xmlns='http://chesspark.com/xml/chesspark-01'/></query></iq><iq id='981:getallignorelists' type='get'><query xmlns='jabber:iq:privacy'/></iq></body>
"""
        hp = HttpbParse()

        b, e = hp.parse(XML)

        # need tests here
        self.failUnless(e[0]==u"<iq type='get' id='980:getprefs'><query xmlns='jabber:iq:private'><preferences xmlns='http://chesspark.com/xml/chesspark-01'/></query></iq>", 'invalid xml')
        self.failUnless(e[1]==u"<iq type='get' id='981:getallignorelists'><query xmlns='jabber:iq:privacy'/></iq>", 'invalid xml')
        

    def testParseEscapedAttribute(self):
        XML = """<body rid='4019888743' xmlns='http://jabber.org/protocol/httpbind' sid='948972a64d524f862107cdbd748d1d16'><presence from='dude@example.com' to='room@conf.example.com/D&apos;Artagnan Longfellow'/></body>"""

        hp = HttpbParse()

        b, e = hp.parse(XML)

        ex = "<presence to='room@conf.example.com/D&apos;Artagnan Longfellow' from='dude@example.com'/>"
        self.assertEquals(e[0], ex)


    def testPrefixes(self):
        XML = """<body rid='384852951' xmlns='http://jabber.org/protocol/httpbind' sid='e46501b24abd334c062598498a8e02ba'><auth xmlns='urn:ietf:params:xml:ns:xmpp-sasl' mechanism='DIGEST-MD5'/></body>"""

        hp = HttpbParse()

        b, e = hp.parse(XML)

        self.failUnless(e[0]==u"<auth xmlns='urn:ietf:params:xml:ns:xmpp-sasl' mechanism='DIGEST-MD5'/>", 'invalid xml')

    def testPrefixesLang(self):
        XML = """<body rid='384852951' xmlns='http://jabber.org/protocol/httpbind' sid='e46501b24abd334c062598498a8e02ba'><message xml:lang='fr' to='test@test.com'><body>test</body></message></body>"""

        hp = HttpbParse()

        b, e = hp.parse(XML)
        self.failUnless(e[0]==u"<message to='test@test.com' xml:lang='fr'><body>test</body></message>", 'invalid xml')



    def testEscapedCDATA(self):
        XML = """<body rid='384852951' xmlns='http://jabber.org/protocol/httpbind' sid='e46501b24abd334c062598498a8e02ba'><message><body>&gt; </body></message></body>"""

        hp = HttpbParse()

        b, e = hp.parse(XML)

        XML = """ <body rid='1484853516' xmlns='http://jabber.org/protocol/httpbind' sid='4dc131a03346bf94b0d2565dda02de36'><message to='dev@chat.chesspark.com' from='jack@chesspark.com/cpc' type='groupchat' id='2900'><body xmlns='jabber:client'>i type &gt; and i see &gt;&gt;&gt;</body></message></body>"""

        hp = HttpbParse()

        b, e = hp.parse(XML)

        self.failUnless(e[0]==u"<message to='dev@chat.chesspark.com' from='jack@chesspark.com/cpc' id='2900' type='groupchat'><body xmlns='jabber:client'>i type &gt; and i see &gt;&gt;&gt;</body></message>", 'Invalid Xml')


    def testCDATA(self):
        XML = """<body rid='3116008962' xmlns='http://jabber.org/protocol/httpbind' sid='88be95e7ebbd8c12465e311ce73fb8ac'><response xmlns='urn:ietf:params:xml:ns:xmpp-sasl'>dXNlcm5hbWU9InRvZnUiLHJlYWxtPSJkZXYuY2hlc3NwYXJrLmNvbSIsbm9uY2U9Ik5SaW5HQkNaWjg0U09Ea1BzMWpxd1E9PSIsY25vbmNlPSJkNDFkOGNkOThmMDBiMjA0ZTk4MDA5OThlY2Y4NDI3ZSIsbmM9IjAwMDAwMDAxIixxb3A9ImF1dGgiLGRpZ2VzdC11cmk9InhtcHAvZGV2LmNoZXNzcGFyay5jb20iLHJlc3BvbnNlPSIxNGQ3NWE5YmU2MzdkOTdkOTM1YjU2Y2M4ZWZhODk4OSIsY2hhcnNldD0idXRmLTgi</response></body>"""

        hp = HttpbParse()

        b, e = hp.parse(XML)

        self.failUnless(e[0]==u"<response xmlns='urn:ietf:params:xml:ns:xmpp-sasl'>dXNlcm5hbWU9InRvZnUiLHJlYWxtPSJkZXYuY2hlc3NwYXJrLmNvbSIsbm9uY2U9Ik5SaW5HQkNaWjg0U09Ea1BzMWpxd1E9PSIsY25vbmNlPSJkNDFkOGNkOThmMDBiMjA0ZTk4MDA5OThlY2Y4NDI3ZSIsbmM9IjAwMDAwMDAxIixxb3A9ImF1dGgiLGRpZ2VzdC11cmk9InhtcHAvZGV2LmNoZXNzcGFyay5jb20iLHJlc3BvbnNlPSIxNGQ3NWE5YmU2MzdkOTdkOTM1YjU2Y2M4ZWZhODk4OSIsY2hhcnNldD0idXRmLTgi</response>", 'Invalid xml')



    def testPrefsCdata(self):

        XML = """<body rid='4017760695' xmlns='http://jabber.org/protocol/httpbind' sid='74a730628186b053a953999bc2ae7dba'>
      <iq id='6161:setprefs' type='set' xmlns='jabber:client'>
        <query xmlns='jabber:iq:private'>
          <preferences xmlns='http://chesspark.com/xml/chesspark-01'>
            <statuses>
              <away>test2</away>
              <available>test1</available>
            </statuses>
            <favorite-channels>
              <channel jid='asdf@chat.chesspark.com' autojoin='no'/>
              <channel jid='focus@chat.chesspark.com' autojoin='no'/>
              <channel jid='help@chat.chesspark.com' autojoin='no'/>
            </favorite-channels>
            <time-controls/>
            <searchfilters>
              <filter node='play'>
                <variant name='standard'/>
              </filter>
              <filter open='yes' node='watch'>
                <computer/>
              </filter>
              <filter node='adjourned'>
                <computer/>
              </filter>
              <filter node='myads'>
                <computer/>
              </filter>
            </searchfilters>
            <loginrooms>
              <room>pro@chat.chesspark.com</room>
            </loginrooms>
            <noinitialroster/>
            <boardsize size='61'/>
            <volume setting='100'/>
            <hidewelcomedialog/>
            <showoffline/>
            <showavatars/>
            <showmucpresenceinchat/>
            <hideparticipants/>
            <newlineonshift/>
            <nochatnotify/>
            <no-gameboard-autoresize/>
            <messagewhenplaying/>
            <hidegamefinderhelp/>
            <hidewarningondisconnect/>
            <disablesounds/>
            <nogamesearchonlogin/>
          </preferences>
        </query>
      </iq>
    </body>"""


        hp = HttpbParse()

        b, e = hp.parse(XML)

        self.failUnless(e[0]==u"<iq xmlns='jabber:client' type='set' id='6161:setprefs'>\n        <query xmlns='jabber:iq:private'>\n          <preferences xmlns='http://chesspark.com/xml/chesspark-01'>\n            <statuses>\n              <away>test2</away>\n              <available>test1</available>\n            </statuses>\n            <favorite-channels>\n              <channel jid='asdf@chat.chesspark.com' autojoin='no'/>\n              <channel jid='focus@chat.chesspark.com' autojoin='no'/>\n              <channel jid='help@chat.chesspark.com' autojoin='no'/>\n            </favorite-channels>\n            <time-controls/>\n            <searchfilters>\n              <filter node='play'>\n                <variant name='standard'/>\n              </filter>\n              <filter node='watch' open='yes'>\n                <computer/>\n              </filter>\n              <filter node='adjourned'>\n                <computer/>\n              </filter>\n              <filter node='myads'>\n                <computer/>\n              </filter>\n            </searchfilters>\n            <loginrooms>\n              <room>pro@chat.chesspark.com</room>\n            </loginrooms>\n            <noinitialroster/>\n            <boardsize size='61'/>\n            <volume setting='100'/>\n            <hidewelcomedialog/>\n            <showoffline/>\n            <showavatars/>\n            <showmucpresenceinchat/>\n            <hideparticipants/>\n            <newlineonshift/>\n            <nochatnotify/>\n            <no-gameboard-autoresize/>\n            <messagewhenplaying/>\n            <hidegamefinderhelp/>\n            <hidewarningondisconnect/>\n            <disablesounds/>\n            <nogamesearchonlogin/>\n          </preferences>\n        </query>\n      </iq>", 'invalid xml')
