# Some code from idavoll, thanks Ralph!!
NS_XMPP_STANZAS = "urn:ietf:params:xml:ns:xmpp-stanzas"



conditions = {
	'bad-request':				{'code': '400', 'type': 'modify'},
	'not-authorized':			{'code': '401', 'type': 'cancel'},
	'item-not-found':			{'code': '404', 'type': 'cancel'},
	'not-acceptable':			{'code': '406', 'type': 'modify'},
	'conflict':					{'code': '409', 'type': 'cancel'},
	'internal-server-error':	{'code': '500', 'type': 'wait'},
	'feature-not-implemented':	{'code': '501', 'type': 'cancel'},
	'service-unavailable':		{'code': '503', 'type': 'cancel'},
}

def error_from_iq(iq, condition, text = '', type = None):
	iq.swapAttributeValues("to", "from")
	iq["type"] = 'error'
	e = iq.addElement("error")

	c = e.addElement((NS_XMPP_STANZAS, condition), NS_XMPP_STANZAS)

	if type == None:
		type = conditions[condition]['type']

	code = conditions[condition]['code']

	e["code"] = code
	e["type"] = type

	if text:
		t = e.addElement((NS_XMPP_STANZAS, "text"), NS_XMPP_STANZAS, text)

	return iq
