"""
 session stuff for jabber connections

"""
from twisted.internet import defer,  reactor
from twisted.python import failure, log
from twisted.web import server
from twisted.names.srvconnect import SRVConnector

try:
    from twisted.words.xish import domish, xmlstream
    from twisted.words.protocols import jabber as jabber_protocol
except ImportError:
    from twisted.xish import domish, xmlstream


import traceback
import os
import warnings
from punjab import jabber
from punjab.xmpp import ns

import time
import error

try:
    from twisted.internet import ssl
except ImportError:
    ssl = None
if ssl and not ssl.supported:
    ssl = None
if not ssl:
    log.msg("SSL ERROR: You do not have ssl support this may cause problems with tls client connections.")



class XMPPClientConnector(SRVConnector):
    """
    A jabber connection to find srv records for xmpp client connections.
    """
    def __init__(self, client_reactor, domain, factory):
        """ Init """
        if isinstance(domain, unicode):
            warnings.warn(
                "Domain argument to XMPPClientConnector should be bytes, "
                "not unicode",
                stacklevel=2)
            domain = domain.encode('ascii')
        SRVConnector.__init__(self, client_reactor, 'xmpp-client', domain, factory)
        self.timeout = [1,3]

    def pickServer(self):
        """
        Pick a server and port to make the connection.
        """
        host, port = SRVConnector.pickServer(self)

        if port == 5223 and ssl:
            context = ssl.ClientContextFactory()
            context.method = ssl.SSL.SSLv23_METHOD

            self.connectFuncName = 'connectSSL'
            self.connectFuncArgs = (context,)
        return host, port

def make_session(pint, attrs, session_type='BOSH'):
    """
    pint  - punjab session interface class
    attrs - attributes sent from the body tag
    """

    s    = Session(pint, attrs)

    if pint.v:
        log.msg('================================== %s connect to %s:%s ==================================' % (str(time.time()),s.hostname,s.port))

    connect_srv = s.connect_srv
    if attrs.has_key('route'):
        connect_srv = False
    if s.hostname in ['localhost', '127.0.0.1']:
        connect_srv = False
    if not connect_srv:
        reactor.connectTCP(s.hostname, s.port, s, bindAddress=pint.bindAddress)
    else:
        connector = XMPPClientConnector(reactor, s.hostname, s)
        connector.connect()
    # timeout
    reactor.callLater(s.inactivity, s.checkExpired)

    pint.sessions[s.sid] = s

    return s, s.waiting_requests[0].deferred


class WaitingRequest(object):
    """A helper object for managing waiting requests."""

    def __init__(self, deferred, delayedcall, timeout = 30, startup = False, rid = None):
        """ """
        self.deferred    = deferred
        self.delayedcall = delayedcall
        self.startup     = startup
        self.timeout     = timeout
        self.wait_start  = time.time()
        self.rid         = rid

    def doCallback(self, data):
        """ """
        self.deferred.callback(data)

    def doErrback(self, data):
        """ """
        self.deferred.errback(data)


class Session(jabber.JabberClientFactory, server.Session):
    """ Jabber Client Session class for client XMPP connections. """
    def __init__(self, pint, attrs):
        """
        Initialize the session
        """
        if attrs.has_key('charset'):
            self.charset = str(attrs['charset'])
        else:
            self.charset = 'utf-8'

        self.to    = attrs['to']
        self.port  = 5222
        self.inactivity = 900
        if self.to != '' and self.to.find(":") != -1:
            # Check if port is in the 'to' string
            to, port = self.to.split(':')

            if port:
                self.to   = to
                self.port = int(port)
            else:
                self.port = 5222

        self.sid = "".join("%02x" % ord(i) for i in os.urandom(20))

        jabber.JabberClientFactory.__init__(self, self.to, pint.v)
        server.Session.__init__(self, pint, self.sid)
        self.pint  = pint

        self.attrs = attrs
        self.s     = None

        self.elems = []
        rid        = int(attrs['rid'])

        self.waiting_requests = []
        self.use_raw = attrs.get('raw', False)

        self.raw_buffer = u""
        self.xmpp_node  = ''
        self.success    = 0
        self.mechanisms = []
        self.xmlstream  = None
        self.features   = None
        self.session    = None

        self.cache_data = {}
        self.verbose    = self.pint.v
        self.noisy      = self.verbose

        self.version = attrs.get('version', 0.0)

        self.key = attrs.get('newkey')

        self.wait  = int(attrs.get('wait', 0))

        self.hold  = int(attrs.get('hold', 0))
        self.inactivity = int(attrs.get('inactivity', 900)) # default inactivity 15 mins

        if attrs.has_key('window'):
            self.window  = int(attrs['window'])
        else:
            self.window  = self.hold + 2

        if attrs.has_key('polling'):
            self.polling  = int(attrs['polling'])
        else:
            self.polling  = 0

        if attrs.has_key('port'):
            self.port = int(attrs['port'])

        if attrs.has_key('hostname'):
            self.hostname = attrs['hostname']
        else:
            self.hostname = self.to

        self.use_raw = getattr(pint, 'use_raw', False) # use raw buffers

        self.connect_srv = getattr(pint, 'connect_srv', True)

        self.secure = attrs.has_key('secure') and attrs['secure'] == 'true'
        self.authenticator.useTls = self.secure

        if attrs.has_key('route'):
            if attrs['route'].startswith("xmpp:"):
                self.route = attrs['route'][5:]
                if self.route.startswith("//"):
                    self.route = self.route[2:]

                # route format change, see http://www.xmpp.org/extensions/xep-0124.html#session-request
                rhostname, rport = self.route.split(":")
                self.port = int(rport)
                self.hostname = rhostname
                self.resource = ''
            else:
                raise error.Error('internal-server-error')


        self.authid      = 0
        self.rid         = rid + 1
        self.connected   = 0 # number of clients connected on this session

        self.notifyOnExpire(self.onExpire)
        self.stream_error = None
        if pint.v:
            log.msg('Session Created : %s %s' % (str(self.sid),str(time.time()), ))
        self.stream_error_called = False
        self.addBootstrap(xmlstream.STREAM_START_EVENT, self.streamStart)
        self.addBootstrap(xmlstream.STREAM_CONNECTED_EVENT, self.connectEvent)
        self.addBootstrap(xmlstream.STREAM_ERROR_EVENT, self.streamError)
        self.addBootstrap(xmlstream.STREAM_END_EVENT, self.connectError)

        # create the first waiting request
        d = defer.Deferred()
        timeout = 30
        rid = self.rid - 1
        self.appendWaitingRequest(d, rid,
                                  timeout=timeout,
                                  poll=self._startup_timeout,
                                  startup=True,
                                  )

    def rawDataIn(self, buf):
        """ Log incoming data on the xmlstream """
        if self.pint and self.pint.v:
            try:
                log.msg("SID: %s => RECV: %r" % (self.sid, buf,))
            except:
                log.err()
        if self.use_raw and self.authid:
            if type(buf) == type(''):
                buf = unicode(buf, 'utf-8')
            # add some raw data
            self.raw_buffer = self.raw_buffer + buf


    def rawDataOut(self, buf):
        """ Log outgoing data on the xmlstream """
        try:
            log.msg("SID: %s => SEND: %r" % (self.sid, buf,))
        except:
            log.err()

    def _wrPop(self, data, i=0):
        """Pop off a waiting requst, do callback, and cache request
        """
        wr = self.waiting_requests.pop(i)
        wr.doCallback(data)
        self._cacheData(wr.rid, data)

    def clearWaitingRequests(self, hold = 0):
        """clear number of requests given

           hold - number of requests to clear, default is all
        """
        while len(self.waiting_requests) > hold:
            self._wrPop([])

    def _wrError(self, err, i = 0):
        wr = self.waiting_requests.pop(i)
        wr.doErrback(err)


    def appendWaitingRequest(self, d, rid, timeout=None, poll=None, startup=False):
        """append waiting request
        """
        if timeout is None:
            timeout = self.wait
        if poll is None:
            poll = self._pollTimeout
        self.waiting_requests.append(
            WaitingRequest(d,
                           poll,
                           timeout = timeout,
                           rid = rid,
                           startup=startup))

    def returnWaitingRequests(self):
        """return a waiting request
        """
        while len(self.elems) > 0 and len(self.waiting_requests) > 0:
            data = self.elems
            self.elems = []
            self._wrPop(data)


    def onExpire(self):
        """ When the session expires call this. """
        if 'onExpire' in dir(self.pint):
            self.pint.onExpire(self.sid)
        if self.verbose and not getattr(self, 'terminated', False):
            log.msg('SESSION -> We have expired', self.sid, self.rid, self.waiting_requests)
        self.disconnect()

    def terminate(self):
        """Terminates the session."""
        self.wait = 0
        self.terminated = True
        if self.verbose:
            log.msg('SESSION -> Terminate')

        # if there are any elements hanging around and waiting
        # requests, send those off
        self.returnWaitingRequests()

        self.clearWaitingRequests()

        try:
            self.expire()
        except:
            self.onExpire()


        return defer.succeed(self.elems)

    def poll(self, d = None, rid = None):
        """Handles the responses to requests.

        This function is called for every request except session setup
        and session termination.  It handles the reply portion of the
        request by returning a deferred which will get called back
        when there is data or when the wait timeout expires.
        """
        # queue this request
        if d is None:
            d = defer.Deferred()
        if self.pint.error:
            d.addErrback(self.pint.error)
        if not rid:
            rid = self.rid - 1
        self.appendWaitingRequest(d, rid)
        # check if there is any data to send back to a request
        self.returnWaitingRequests()

        # make sure we aren't queueing too many requests
        self.clearWaitingRequests(self.hold)
        return d

    def _pollTimeout(self, d):
        """Handle request timeouts.

        Since the timeout function is called, we must return an empty
        reply as there is no data to send back.
        """
        # find the request that timed out and reply
        pop_eye = []
        for i in range(len(self.waiting_requests)):
            if self.waiting_requests[i].deferred == d:
                pop_eye.append(i)
                self.touch()

        for i in pop_eye:
            self._wrPop([],i)


    def _pollForId(self, d):
        if self.xmlstream.sid:
            self.authid = self.xmlstream.sid
        self._pollTimeout(d)



    def connectEvent(self, xs):

        self.version =  self.authenticator.version
        self.xmlstream = xs
        if self.pint.v:
            # add logging for verbose output

            self.xmlstream.rawDataOutFn = self.rawDataOut
        self.xmlstream.rawDataInFn = self.rawDataIn

        if self.version == '1.0':
            self.xmlstream.addObserver("/features", self.featuresHandler)



    def streamStart(self, xs):
        """
        A xmpp stream has started
        """
        # This is done to fix the stream id problem, I should submit a bug to twisted bugs

        try:

            self.authid    = self.xmlstream.sid

            if not self.attrs.has_key('no_events'):

                self.xmlstream.addOnetimeObserver("/auth", self.stanzaHandler)
                self.xmlstream.addOnetimeObserver("/response", self.stanzaHandler)
                self.xmlstream.addOnetimeObserver("/success", self._saslSuccess)
                self.xmlstream.addOnetimeObserver("/failure", self._saslError)

                self.xmlstream.addObserver("/iq/bind", self.bindHandler)
                self.xmlstream.addObserver("/bind", self.stanzaHandler)

                self.xmlstream.addObserver("/challenge", self.stanzaHandler)
                self.xmlstream.addObserver("/message",  self.stanzaHandler)
                self.xmlstream.addObserver("/iq",  self.stanzaHandler)
                self.xmlstream.addObserver("/presence",  self.stanzaHandler)
                # TODO - we should do something like this
                # self.xmlstream.addObserver("/*",  self.stanzaHandler)

        except:
            log.err(traceback.print_exc())
            self._wrError(error.Error("remote-connection-failed"))
            self.disconnect()


    def featuresHandler(self, f):
        """
        handle stream:features
        """
        f.prefixes   = ns.XMPP_PREFIXES.copy()

        #check for tls
        self.f = {}
        for feature in f.elements():
            self.f[(feature.uri, feature.name)] = feature

        starttls = (ns.TLS_XMLNS, 'starttls') in self.f

        initializers   = getattr(self.xmlstream, 'initializers', [])
        self.features = f
        self.xmlstream.features = f

        # There is a tls initializer added by us, if it is available we need to try it
        if len(initializers)>0 and starttls:
            self.secure = True

        if self.authid is None:
            self.authid = self.xmlstream.sid


        # If we get tls, then we should start tls, wait and then return
        # Here we wait, the tls initializer will start it
        if starttls and self.secure:
            if self.verbose:
                log.msg("Wait until starttls is completed.")
                log.msg(initializers)
            return
        self.elems.append(f)
        if len(self.waiting_requests) > 0:
            self.returnWaitingRequests()
            self.elems = [] # reset elems
            self.raw_buffer = u"" # reset raw buffer, features should not be in it

    def bindHandler(self, stz):
        """bind debugger for punjab, this is temporary! """
        if self.verbose:
            try:
                log.msg('BIND: %s %s' % (str(self.sid), str(stz.bind.jid)))
            except:
                log.err()
        if self.use_raw:
            self.raw_buffer = stz.toXml()

    def stanzaHandler(self, stz):
        """generic stanza handler for httpbind and httppoll"""
        stz.prefixes = ns.XMPP_PREFIXES
        if self.use_raw and self.authid:
            stz = domish.SerializedXML(self.raw_buffer)
            self.raw_buffer = u""

        self.elems.append(stz)
        if self.waiting_requests and len(self.waiting_requests) > 0:
            # if there are any waiting requests, give them all the
            # data so far, plus this new data
            self.returnWaitingRequests()


    def _startup_timeout(self, d):
        # this can be called if connection failed, or if we connected
        # but never got a stream features before the timeout
        if self.pint.v:
            log.msg('================================== %s %s startup timeout ==================================' % (str(self.sid), str(time.time()),))

        for i in range(len(self.waiting_requests)):
            if self.waiting_requests[i].deferred == d:
                # check if we really failed or not
                if self.authid:
                    self._wrPop(self.elems, i=i)
                else:
                    self._wrError(error.Error("remote-connection-failed"), i=i)


    def buildRemoteError(self, err_elem=None):
        # This may not be a stream error, such as an XML parsing error.
        # So expose it as remote-connection-failed.
        err = 'remote-connection-failed'
        if err_elem is not None:
            # This is an actual stream:error.  Create a remote-stream-error to encapsulate it.
            err = 'remote-stream-error'
        e = error.Error(err)
        e.error_stanza = err
        e.children = []
        if err_elem is not None:
            e.children.append(err_elem)
        return e

    def streamError(self, streamerror):
        """called when we get a stream:error stanza"""
        self.stream_error_called = True
        try:
            err_elem = streamerror.value.getElement()
        except AttributeError:
            err_elem = None

        e = self.buildRemoteError(err_elem)

        do_expire = True

        if len(self.waiting_requests) > 0:
            wr = self.waiting_requests.pop(0)
            wr.doErrback(e)
        else: # need to wait for a new request and then expire
            do_expire = False

        if self.pint and self.pint.sessions.has_key(self.sid):
            if do_expire:
                try:
                    self.expire()
                except:
                    self.onExpire()
            else:
                s = self.pint.sessions.get(self.sid)
                s.stream_error = e

    def connectError(self, reason):
        """called when we get disconnected"""
        if self.stream_error_called: return
        # Before Twisted 11.x the xmlstream object was passed instead of the
        # disconnect reason. See http://twistedmatrix.com/trac/ticket/2618
        if not isinstance(reason, failure.Failure):
            reason_str = 'Reason unknown'
        else:
            reason_str = str(reason)

        # If the connection was established and lost, then we need to report
        # the error back to the client, since he needs to reauthenticate.
        # FIXME: If the connection was lost before anything happened, we could
        # silently retry instead.
        if self.verbose:
            log.msg('connect ERROR: %s' % reason_str)

        self.stopTrying()

        e = error.Error('remote-connection-failed')

        do_expire = True

        if self.waiting_requests:
            wr = self.waiting_requests.pop(0)
            wr.doErrback(e)
        else: # need to wait for a new request and then expire
            do_expire = False

        if self.pint and self.pint.sessions.has_key(self.sid):
            if do_expire:
                try:
                    self.expire()
                except:
                    self.onExpire()
            else:
                s = self.pint.sessions.get(self.sid)
                s.stream_error = e


    def sendRawXml(self, obj):
        """
        Send a raw xml string, not a domish.Element
        """
        self.touch()
        self._send(obj)


    def _send(self, xml):
        """
        Send valid data over the xmlstream
        """
        if self.xmlstream: # FIXME this happens on an expired session and the post has something to send
            if isinstance(xml, domish.Element):
                xml.localPrefixes = {}
            self.xmlstream.send(xml)

    def _removeObservers(self, typ = ''):
        if typ == 'event':
            observers = self.xmlstream._eventObservers
        else:
            observers = self.xmlstream._xpathObservers
        emptyLists = []
        for priority, priorityObservers in observers.iteritems():
            for query, callbacklist in priorityObservers.iteritems():
                callbacklist.callbacks = []
                emptyLists.append((priority, query))

        for priority, query in emptyLists:
            del observers[priority][query]

    def disconnect(self):
        """
        Disconnect from the xmpp server.
        """
        if not getattr(self, 'xmlstream',None):
            return

        if self.xmlstream:
            #sh = "<presence type='unavailable' xmlns='jabber:client'/>"
            sh = "</stream:stream>"
            self.xmlstream.send(sh)

        self.stopTrying()
        if self.xmlstream:
            self.xmlstream.transport.loseConnection()

            del self.xmlstream
        self.connected = 0
        self.pint      = None
        self.elems     = []

        if self.waiting_requests:
            self.clearWaitingRequests()
            del self.waiting_requests
        self.mechanisms = None
        self.features   = None



    def checkExpired(self):
        """
        Check if the session or xmpp connection has expired
        """
        # send this so we do not timeout from servers
        if getattr(self, 'xmlstream', None):
            self.xmlstream.send(' ')
        if self.inactivity is None:
            wait = 900
        elif self.inactivity == 0:
            wait = time.time()

        else:
            wait = self.inactivity

        if self.waiting_requests and len(self.waiting_requests)>0:
            wait += self.wait # if we have pending requests we need to add the wait time

        if time.time() - self.lastModified > wait+(0.1):
            if self.site.sessions.has_key(self.uid):
                self.terminate()
            else:
                pass

        else:
            reactor.callLater(wait, self.checkExpired)


    def _cacheData(self, rid, data):
        if len(self.cache_data.keys())>=3:
            # remove the first one in
            keys = self.cache_data.keys()
            keys.sort()
            del self.cache_data[keys[0]]

        self.cache_data[int(rid)] = data

# This stuff will leave when SASL and TLS are implemented correctly
# session stuff

    def _sessionResultEvent(self, iq):
        """ """
	if len(self.waiting_requests)>0:
		wr = self.waiting_requests.pop(0)
		d  = wr.deferred
	else:
		d = None

        if iq["type"] == "result":
            if d:
                d.callback(self)
        else:
            if d:
                d.errback(self)


    def _saslSuccess(self, s):
        """ """
        self.success = 1
        self.s = s
        # return success to the client
        if len(self.waiting_requests)>0:
            self._wrPop([s])

        self.authenticator._reset()
        if self.use_raw:
            self.raw_buffer = u""



    def _saslError(self, sasl_error, d = None):
        """ SASL error """

        if d:
            d.errback(self)
        if len(self.waiting_requests)>0:
            self._wrPop([sasl_error])
