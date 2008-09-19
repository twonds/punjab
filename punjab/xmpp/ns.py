
NS_CLIENT   = 'jabber:client'
NS_ROSTER   = 'jabber:iq:roster'
NS_AUTH     = 'jabber:iq:auth'
NS_STREAMS  = 'http://etherx.jabber.org/streams'
NS_XMPP_TLS = 'urn:ietf:params:xml:ns:xmpp-tls'
NS_COMMANDS = 'http://jabber.org/protocol/commands'

TLS_XMLNS = 'urn:ietf:params:xml:ns:xmpp-tls'
SASL_XMLNS = 'urn:ietf:params:xml:ns:xmpp-sasl'
BIND_XMLNS = 'urn:ietf:params:xml:ns:xmpp-bind'
SESSION_XMLNS = 'urn:ietf:params:xml:ns:xmpp-session'
STREAMS_XMLNS  = 'urn:ietf:params:xml:ns:xmpp-streams'

IQ_GET      = "/iq[@type='get']"
IQ_SET      = "/iq[@type='set']"

IQ_GET_AUTH = IQ_GET+"/query[@xmlns='%s']" % (NS_AUTH,)
IQ_SET_AUTH = IQ_SET+"/query[@xmlns='%s']" % (NS_AUTH,)


XMPP_PREFIXES = {NS_STREAMS:'stream'}
#                 NS_COMMANDS: 'commands'}

