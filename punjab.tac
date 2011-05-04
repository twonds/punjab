# punjab tac file
# tac documentation is at the following URL:
# http://twistedmatrix.com/documents/current/core/howto/application.html
from twisted.web import server, resource, static
from twisted.application import service, internet

from punjab.httpb  import Httpb, HttpbService

root = static.File("./html")

# uncomment only one of the bosh lines, use_raw does no xml
# parsing/serialization but is potentially less reliable
#bosh = HttpbService(1, use_raw=True)
bosh = HttpbService(1)

# You can limit servers with a whitelist.
# The whitelist is a list of strings to match domain names.
# bosh.white_list = ['jabber.org', 'thetofu.com']
# or a black list
# bosh.block_list = ['jabber.org', '.thetofu.com']

root.putChild('http-bind', resource.IResource(bosh))


site  = server.Site(root)

application = service.Application("punjab")
internet.TCPServer(5280, site).setServiceParent(application)

# To run this simply to twistd -y punjab.tac
