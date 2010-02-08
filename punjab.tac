# punjab tac file
from twisted.web import server, resource, static
from twisted.application import service, internet

from punjab.httpb  import Httpb, HttpbService

root = static.File("./html")


#b = resource.IResource(HttpbService(1, use_raw=True))
b = resource.IResource(HttpbService(1))
root.putChild('http-bind', b)


site  = server.Site(root)

application = service.Application("punjab")
internet.TCPServer(5280, site).setServiceParent(application)

