"""
 http binding interface
"""
from twisted.python import components
from twisted.web import server, resource
from twisted.internet import defer, task
from twisted.python import log

from zope.interface import Interface, implements

try:
    from twisted.words.xish import domish
except ImportError:
    from twisted.xish import domish

import hashlib, time
import error
from session import make_session
import punjab
from punjab.xmpp import ns


NS_BIND = 'http://jabber.org/protocol/httpbind'
NS_FEATURES = 'http://etherx.jabber.org/streams'
NS_XMPP = 'urn:xmpp:xbosh'

class DummyElement:
    """
    dummy element for a quicker parse
    """
    # currently not used
    def __init__(self, *args, **kwargs):

        self.children = []



class HttpbElementStream(domish.ExpatElementStream):
    """
    add rawXml to the elements
    """

    def __init__(self, prefixes=None):
        domish.ExpatElementStream.__init__(self)
        self.prefixes = {}
        if prefixes:
            self.prefixes.update(prefixes)
        self.prefixes.update(domish.G_PREFIXES)
        self.prefixStack = [domish.G_PREFIXES.values()]
        self.prefixCounter = 0


    def getPrefix(self, uri):
        if not self.prefixes.has_key(uri):
            self.prefixes[uri] = "xn%d" % (self.prefixCounter)
            self.prefixCounter = self.prefixCounter + 1
        return self.prefixes[uri]

    def prefixInScope(self, prefix):
        stack = self.prefixStack
        for i in range(-1, (len(self.prefixStack)+1) * -1, -1):
            if prefix in stack[i]:
                return True
        return False

    def _onStartElement(self, name, attrs):
        # Generate a qname tuple from the provided name
        attr_str   = ''
        defaultUri = None
        uri        = None
        qname = name.split(" ")
        if len(qname) == 1:
            qname = ('', name)
            currentUri = None
        else:
            currentUri = qname[0]
        if self.currElem:
            defaultUri = self.currElem.defaultUri
            uri = self.currElem.uri

        if not defaultUri and currentUri in self.defaultNsStack:
            defaultUri = self.defaultNsStack[1]

        if defaultUri and currentUri != defaultUri:

            raw_xml = u"""<%s xmlns='%s'%s""" % (qname[1], qname[0], '%s')

        else:
            raw_xml = u"""<%s%s""" % (qname[1], '%s')


        # Process attributes

        for k, v in attrs.items():
            if k.find(" ") != -1:
                aqname = k.split(" ")
                attrs[(aqname[0], aqname[1])] = v

                attr_prefix = self.getPrefix(aqname[0])
                if not self.prefixInScope(attr_prefix):
                    attr_str = attr_str + " xmlns:%s='%s'" % (attr_prefix,
                                                              aqname[0])
                    self.prefixStack[-1].append(attr_prefix)
                attr_str = attr_str + " %s:%s='%s'" % (attr_prefix,
                                                       aqname[1],
                                                       domish.escapeToXml(v,
                                                                          True))
                del attrs[k]
            else:
                v = domish.escapeToXml(v, True)
                attr_str = attr_str + " " + k + "='" + v + "'"

        raw_xml = raw_xml % (attr_str,)

        # Construct the new element
        e = domish.Element(qname, self.defaultNsStack[-1], attrs, self.localPrefixes)
        self.localPrefixes = {}

        # Document already started
        if self.documentStarted == 1:
            if self.currElem != None:
                if len(self.currElem.children)==0 or isinstance(self.currElem.children[-1], domish.Element):
                    if self.currRawElem[-1] != ">":
                        self.currRawElem = self.currRawElem +">"

                self.currElem.children.append(e)
                e.parent = self.currElem

            self.currRawElem = self.currRawElem + raw_xml
            self.currElem = e
        # New document
        else:
            self.currRawElem = u''
            self.documentStarted = 1
            self.DocumentStartEvent(e)

    def _onEndElement(self, _):
        # Check for null current elem; end of doc
        if self.currElem is None:
            self.DocumentEndEvent()

        # Check for parent that is None; that's
        # the top of the stack
        elif self.currElem.parent is None:
            if len(self.currElem.children)>0:
                self.currRawElem = self.currRawElem + "</"+ self.currElem.name+">"
            else:
                self.currRawElem = self.currRawElem + "/>"
            self.ElementEvent(self.currElem, self.currRawElem)
            self.currElem = None
            self.currRawElem = u''
        # Anything else is just some element in the current
        # packet wrapping up
        else:
            if len(self.currElem.children)==0:
                self.currRawElem = self.currRawElem + "/>"
            else:
                self.currRawElem = self.currRawElem + "</"+ self.currElem.name+">"
            self.currElem = self.currElem.parent

    def _onCdata(self, data):
        if self.currElem != None:
            if len(self.currElem.children)==0:
                self.currRawElem = self.currRawElem + ">" + domish.escapeToXml(data)
                #self.currRawElem = self.currRawElem + ">" + data
            else:
                self.currRawElem = self.currRawElem  + domish.escapeToXml(data)
                #self.currRawElem = self.currRawElem  + data

            self.currElem.addContent(data)

    def _onStartNamespace(self, prefix, uri):
        # If this is the default namespace, put
        # it on the stack
        if prefix is None:
            self.defaultNsStack.append(uri)
        else:
            self.localPrefixes[prefix] = uri

    def _onEndNamespace(self, prefix):
        # Remove last element on the stack
        if prefix is None:
            self.defaultNsStack.pop()

def elementStream():
    """ Preferred method to construct an ElementStream

    Uses Expat-based stream if available, and falls back to Sux if necessary.
    """
    try:
        es = HttpbElementStream()
        return es
    except ImportError:
        if domish.SuxElementStream is None:
            raise Exception("No parsers available :(")
        es = domish.SuxElementStream()
        return es

# make httpb body class, similar to xmlrpclib
#
class HttpbParse:
    """
    An xml parser for parsing the body elements.
    """
    def __init__(self, use_t=False):
        """
        Call reset to initialize object
        """
        self.use_t = use_t # use domish element stream
        self._reset()


    def parse(self, buf):
        """
        Parse incoming xml and return the body and its children in a list
        """
        self.stream.parse(buf)

        # return the doc element and its children in a list
        return self.body, self.xmpp_elements

    def serialize(self, obj):
        """
        Turn object into a string type
        """
        if isinstance(obj, domish.Element):
            obj = obj.toXml()
        return obj

    def onDocumentStart(self, rootelem):
        """
        The body document has started.

        This should be a body.
        """
        if rootelem.name == 'body':
            self.body = rootelem

    def onElement(self, element, raw_element = None):
        """
        A child element has been found.
        """
        if isinstance(element, domish.Element):
            if raw_element:
                self.xmpp_elements.append(raw_element)
            else:
                self.xmpp_elements.append(element)
        else:
            pass

    def _reset(self):
        """
        Setup the parser
        """
        if not self.use_t:
            self.stream = elementStream()
        else:
            self.stream = domish.elementStream()

        self.stream.DocumentStartEvent = self.onDocumentStart
        self.stream.ElementEvent = self.onElement
        self.stream.DocumentEndEvent = self.onDocumentEnd
        self.body = ""
        self.xmpp_elements = []


    def onDocumentEnd(self):
        """
        Body End
        """
        pass

class IHttpbService(Interface):
    """
    Interface for http binding class
    """
    def __init__(self, verbose):
        """ """

    def startSession(self, body):
        """ Start a punjab jabber session """

    def endSession(self, session):
        """ end a punjab jabber session """

    def onExpire(self, session_id):
        """ preform actions based on when the jabber connection expires """

    def parseBody(self, body):
        """ parse a body element """


    def error(self, error):
        """ send a body error element """


    def inSession(self, body):
        """ """

    def getXmppElements(self, body, session):
        """ """



class IHttpbFactory(Interface):
    """
    Factory class for generating binding sessions.
    """
    def startSession(self):
        """ Start a punjab jabber session """

    def endSession(self, session):
        """ end a punjab jabber session """

    def parseBody(self, body):
        """ parse an body element """

    def buildProtocol(self, addr):
        """Return a protocol """



class Httpb(resource.Resource):
    """
    Http resource to handle BOSH requests.
    """
    isLeaf = True
    def __init__(self, service, v = 0):
        """Initialize.
        """
        resource.Resource.__init__(self)
        self.service  = service
        self.hp       = None
        self.children = {}
        self.client   = 0
        self.verbose  = v

        self.polling = self.service.polling or 15

    def render_OPTIONS(self, request):
        request.setHeader('Access-Control-Allow-Origin', '*')
        request.setHeader('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        request.setHeader('Access-Control-Allow-Headers', 'Content-Type')
        request.setHeader('Access-Control-Max-Age', '86400')
        return ""

    def render_GET(self, request):
        """
        GET is not used, print docs.
        """
        request.setHeader('Access-Control-Allow-Origin', '*')
        request.setHeader('Access-Control-Allow-Headers', 'Content-Type')
        return """<html>
                 <body>
                 <a href='http://www.xmpp.org/extensions/xep-0124.html'>XEP-0124</a> - BOSH
                 </body>
               </html>"""

    def render_POST(self, request):
        """
        Parse received xml
        """
        request.setHeader('Access-Control-Allow-Origin', '*')
        request.setHeader('Access-Control-Allow-Headers', 'Content-Type')
        request.content.seek(0, 0)
        if self.service.v:
            log.msg('HEADERS %s:' % (str(time.time()),))
            log.msg(request.received_headers)
            log.msg("HTTPB POST : ")
            log.msg(str(request.content.read()))
            request.content.seek(0, 0)

        self.hp       = HttpbParse()
        try:
            body_tag, xmpp_elements = self.hp.parse(request.content.read())
            self.hp._reset()

            if getattr(body_tag, 'name', '') != "body":
                if self.service.v:
                    log.msg('Client sent bad POST data')
                self.send_http_error(400, request)
                return server.NOT_DONE_YET
        except domish.ParserError:
            log.msg('ERROR: Xml Parse Error')
            log.err()
            self.hp._reset()
            self.send_http_error(400, request)
            return server.NOT_DONE_YET
        except:
            log.err()
            # reset parser, just in case
            self.hp._reset()
            self.send_http_error(400, request)
            return server.NOT_DONE_YET
        else:
            if self.service.inSession(body_tag):
                # sid is an existing session
                if body_tag.getAttribute('rid'):
                    request.rid = body_tag['rid']
                    if self.service.v:
                        log.msg(request.rid)

                s, d = self.service.parseBody(body_tag, xmpp_elements)
                d.addCallback(self.return_httpb, s, request)
            elif body_tag.hasAttribute('sid'):
                if self.service.v:
                    log.msg("no sid is found but the body element has a 'sid' attribute")
                # This is an error, no sid is found but the body element has a 'sid' attribute
                self.send_http_error(404, request)
                return server.NOT_DONE_YET
            else:
                # start session
                s, d = self.service.startSession(body_tag, xmpp_elements)
                d.addCallback(self.return_session, s, request)

            # Add an error back for returned errors
            d.addErrback(self.return_error, request)
        return server.NOT_DONE_YET


    def return_session(self, data, session, request):
        # create body
        if session.xmlstream is None:
            self.send_http_error(200, request, 'remote-connection-failed',
                                 'terminate')
            return server.NOT_DONE_YET

        b = domish.Element((NS_BIND, "body"), localPrefixes = {'xmpp' : NS_XMPP, 'stream' : NS_FEATURES })
        # if we don't have an authid, we have to fail
        if session.authid != 0:
            b['authid'] = session.authid
        else:
            self.send_http_error(500, request, 'internal-server-error',
                                 'terminate')
            return server.NOT_DONE_YET

        b['sid']  = session.sid
        b['wait'] = str(session.wait)
        if session.secure == 0:
            b['secure'] = 'false'
        else:
            b['secure'] = 'true'

        b['inactivity'] = str(session.inactivity)
        b['polling'] = str(self.polling)
        b['requests'] = str(session.hold + 1)
        b['window'] = str(session.window)
        b[(NS_XMPP, 'version')] = '1.0'

        punjab.uriCheck(b, NS_BIND)
        if session.attrs.has_key('content'):
            b['content'] = session.attrs['content']

        # We need to send features
        while len(data) > 0:
            felem = data.pop(0)
            if isinstance(felem, domish.Element):
                b.addChild(felem)
            else:
                b.addRawXml(felem)

        self.return_body(request, b)

    def return_httpb(self, data, session, request):
        # create body
        b = domish.Element((NS_BIND, "body"))
        punjab.uriCheck(b, NS_BIND)
        session.touch()
        if getattr(session,'terminated', False):
            b['type']      = 'terminate'
        if data:
            b.children += data

        self.return_body(request, b, session.charset)


    def return_error(self, e, request):
        echildren = []
        try:
            # TODO - clean this up and make errors better
            if getattr(e.value,'stanza_error',None):
                ec = getattr(e.value, 'children', None)
                if ec:
                    echildren = ec

                self.send_http_error(error.conditions[str(e.value.stanza_error)]['code'],
                                     request,
                                     condition = str(e.value.stanza_error),
                                     typ = error.conditions[str(e.value.stanza_error)]['type'],
                                     children=echildren)

                return  server.NOT_DONE_YET
            elif e.value:
                self.send_http_error(error.conditions[str(e.value)]['code'],
                                     request,
                                     str(e.value),
                                     error.conditions[str(e.value)]['type'])
                return  server.NOT_DONE_YET
            else:
                self.send_http_error(500, request, 'internal-server-error', 'error', e)
        except:
            log.err()
            pass


    def return_body(self, request, b, charset="utf-8"):
        request.setResponseCode(200)
        bxml = b.toXml(prefixes=ns.XMPP_PREFIXES.copy()).encode(charset,'replace')

        request.setHeader('content-type', 'text/xml')
        request.setHeader('content-length', len(bxml))
        if self.service.v:
            log.msg('\n\nRETURN HTTPB %s:' % (str(time.time()),))
            log.msg(bxml)
            if getattr(request, 'rid', None):
                log.msg(request.rid)
        request.write(bxml)
        request.finish()

    def send_http_error(self, code, request, condition = 'undefined-condition', typ = 'terminate', data = '', charset = 'utf-8', children=None):
        request.setResponseCode(int(code))
        xml_prefixes = ns.XMPP_PREFIXES.copy()

        b = domish.Element((NS_BIND, "body"))
        if condition:
            b['condition'] = str(condition)
        else:
            b['condition'] = 'undefined-condition'

        if typ:
            b['type']      = str(typ)
        else:
            b['type']      = 'terminate'
        punjab.uriCheck(b, NS_BIND)
        bxml = b.toXml(prefixes=xml_prefixes).encode(charset, 'replace')

        if children:
            b.children += children

        if self.service.v:
            log.msg('HTTPB Error %d' %(int(code),))

        if int(code) != 400 and int(code) != 404 and int(code) != 403:
            if data != '':
                if condition == 'see-other-uri':
                    b.addElement('uri', None, content = str(data))
                else:
                    t = b.addElement('text', content = str(data))
                    t['xmlns'] = 'urn:ietf:params:xml:ns:xmpp-streams'

            bxml = b.toXml(prefixes=xml_prefixes).encode(charset, 'replace')
            if self.service.v:
                log.msg('HTTPB Return Error: ' + str(code) + ' -> ' + bxml)
            request.setHeader("content-type", "text/xml")
            request.setHeader("content-length", len(bxml))
            request.write(bxml)
        else:
            request.setHeader("content-length", "0")
        request.finish()


components.registerAdapter(Httpb, IHttpbService, resource.IResource)


class HttpbService(punjab.Service):

    implements(IHttpbService)

    white_list = []
    black_list = []

    def __init__(self,
                 verbose = 0, polling = 15,
                 use_raw = False, bindAddress=None,
                 session_creator = None):
        if session_creator is not None:
            self.make_session = session_creator
        else:
            self.make_session = make_session
        self.v  = verbose
        self.sessions = {}
        self.polling = polling
        # self.expired  = {}
        self.use_raw  = use_raw

        # run a looping call to do pollTimeouts on sessions
        self.poll_timeouts = task.LoopingCall(self._doPollTimeOuts)

        self.poll_timeouts.start(3) # run every 3 seconds

        self.bindAddress=bindAddress

    def _doPollTimeOuts(self):
        """
        Call poll time outs on sessions that have waited too long.
        """
        time_now = time.time() + 2.9 # need a number to offset the poll timeouts
        for session in self.sessions.itervalues():
            if len(session.waiting_requests)>0:
                for wr in session.waiting_requests:
                    if time_now - wr.wait_start >= wr.timeout:
                        wr.delayedcall(wr.deferred)


    def startSession(self, body, xmpp_elements):
        """ Start a punjab jabber session """

        # look for rid
        if not body.hasAttribute('rid') or body['rid']=='':
            if self.v:
                log.msg('start session called but we had a rid')
            return None, defer.fail(error.NotFound)

        # look for to
        if not body.hasAttribute('to') or body['to']=='':
            return None, defer.fail(error.BadRequest)

        # The target host must match an entry in the white_list. white_list
        # entries beginning with periods will allow subdomains.
        #
        # e.g.: A 'to' of 'foo.example.com' would not match 'example.com' but
        #       would match '.example.com' or '*example.com' or '*.example.com'
        #
        # Or target must not be in black_list. If neither white_list or
        # black_list is present, target is always allowed.
        if self.white_list:
            valid_host = False
            for domain in self.white_list:
                if body['to'] == domain or \
                        (domain[0] == '*' and domain[1] == '.' and\
                             body['to'].endswith(domain[2:])) or \
                        (domain[0] == '*' and \
                             body['to'].endswith(domain[1:])) or \
                        (domain[0] == '.' and \
                             body['to'].endswith(domain[1:])):
                    valid_host = True
                    break
            if not valid_host:
                return None, defer.fail(error.BadRequest)

        if self.black_list:
            valid_host = True
            for domain in self.black_list:
                if body['to'] == domain or \
                        (domain[0] == '*' and domain[1] == '.' and
                         body['to'].endswith(domain[2:])) or \
                        (domain[0] == '*' and \
                         body['to'].endswith(domain[1:])) or \
                        (domain[0] == '.' and \
                         body['to'].endswith(domain[1:])):
                    valid_host = False
                    break
            if not valid_host:
                return None, defer.fail(error.BadRequest)

        # look for wait
        if not body.hasAttribute('wait') or body['wait']=='':
            body['wait'] = 3

        # look for lang
        lang = None
        if not body.hasAttribute("xml:lang") or body['xml:lang']=='':
            for k in body.attributes:
                if isinstance(k, tuple):
                    if str(k[1])=='lang' and body.getAttribute(k) !='':
                        lang = body.getAttribute(k)
        if lang:
            body['lang'] = lang
        if not body.hasAttribute('inactivity'):
            body['inactivity'] = 60
        return self.make_session(self, body.attributes)

    def stopService(self):
        """Perform shutdown procedures."""
        if self.v:
            log.msg("Stopping HTTPB service.")
        self.terminateSessions()
        return defer.succeed(True)

    def terminateSessions(self):
        """Terminate all active sessions."""
        if self.v:
            log.msg('Terminating %d BOSH sessions.' % len(self.sessions))
        for s in self.sessions.values():
            s.terminate()

    def parseBody(self, body, xmpp_elements):
        try:
            # grab session
            if body.hasAttribute('sid'):
                sid = str(body['sid'])
            else:
                if self.v:
                    log.msg('Session ID not found')
                return None, defer.fail(error.NotFound)
            if self.inSession(body):
                s = self.sessions[sid]
                s.touch() # any connection should be a renew on wait
            else:
                if self.v:
                    log.msg('session does not exist?')
                return None, defer.fail(error.NotFound)

            if bool(s.key) != body.hasAttribute('key'):
                # This session is keyed, but there's no key in this packet; or there's
                # a key in this packet, but the session isn't keyed.
                return s, defer.fail(error.Error('item-not-found'))

            # If this session is keyed, validate the next key.
            if s.key:
                key = hashlib.sha1(body['key']).hexdigest()
                next_key = body['key']
                if key != s.key:
                    if self.v:
                        log.msg('Error in key')
                    return s, defer.fail(error.Error('item-not-found'))
                s.key = next_key

            # If there's a newkey in this packet, save it.  Do this after validating the
            # previous key.
            if body.hasAttribute('newkey'):
                s.key = body['newkey']


            # need to check if this is a valid rid (within tolerance)
            if body.hasAttribute('rid') and body['rid']!='':
                if s.cache_data.has_key(int(body['rid'])):
                    s.touch()
                    # implements issue 32 and returns the data returned on a dropped connection
                    return s, defer.succeed(s.cache_data[int(body['rid'])])
                if abs(int(body['rid']) - int(s.rid)) > s.window:
                    if self.v:
                        log.msg('This rid is invalid %s %s ' % (str(body['rid']), str(s.rid),))
                    return  s, defer.fail(error.NotFound)
            else:
                if self.v:
                    log.msg('There is no rid on this request')
                return  s, defer.fail(error.NotFound)

            return s, self._parse(s, body, xmpp_elements)

        except:
            log.err()
            return  s, defer.fail(error.InternalServerError)


    def onExpire(self, session_id):
        """ preform actions based on when the jabber connection expires """
        if self.v:
            log.msg('expire (%s)' % (str(session_id),))
            log.msg(len(self.sessions.keys()))

    def _parse(self, session, body_tag, xmpp_elements):
        # increment the request counter
        session.rid  = session.rid + 1

        if getattr(session, 'stream_error', None) != None:
            # The server previously sent us a stream:error, and has probably closed
            # the connection by now.  Forward the error to the client and terminate
            # the session.
            d = defer.Deferred()
            d.errback(session.stream_error)
            session.elems = []
            session.terminate()
            return d

        # Send received elements from the client to the server.  Do this even for
        # type='terminate'.
        for el in xmpp_elements:
            if isinstance(el, domish.Element):
                # something is wrong here, need to figure out what
                # the xmlns will be lost if this is not done
                # punjab.uriCheck(el,NS_BIND)
                # if el.uri and el.uri != NS_BIND:
                #    el['xmlns'] = el.uri
                # TODO - get rid of this when we stop supporting old versions
                #        of twisted.words
                if el.uri == NS_BIND:
                    el.uri = None
                if el.defaultUri == NS_BIND:
                    el.defaultUri = None

            session.sendRawXml(el)

        if body_tag.hasAttribute('type') and \
           body_tag['type'] == 'terminate':
            return session.terminate()

        # normal request
        return session.poll(None, rid = int(body_tag['rid']))

    def _returnIq(self, cur_session, d, iq):
        """
        A callback from auth iqs
        """
        return cur_session.poll(d)

    def _cbIq(self, iq, cur_session, d):
        """
        A callback from auth iqs
        """

        # session.elems.append(iq)
        return cur_session.poll(d)

    def inSession(self, body):
        """ """
        if body.hasAttribute('sid'):
            if self.sessions.has_key(body['sid']):
                return True
        return False

    def getXmppElements(self, b, session):
        """
        Get waiting xmpp elements
        """
        for i, obj in enumerate(session.msgs):
            m = session.msgs.pop(0)
            b.addChild(m)
        for i, obj in enumerate(session.prs):
            p = session.prs.pop(0)
            b.addChild(p)
        for i, obj in enumerate(session.iqs):
            iq = session.iqs.pop(0)
            b.addChild(iq)

        return b

    def endSession(self, cur_session):
        """ end a punjab jabber session """
        d = cur_session.terminate()
        return d

