from zope.interface import implements
from twisted.python import usage
from twisted.plugin import IPlugin
from twisted.application.service import IServiceMaker

# Due to the directory layout, and the fact that plugin directories aren't
# modules (no __init__.py), this file is named something other than punjab.py,
# to ensure that this import pulls in the right module.
import punjab

class Options(usage.Options):
    optParameters = [
        ('host', None, 'localhost'),
        ('port', None, 5280),
        ('httpb', 'b', "http-bind"),
        ('polling', None, '15'),
        ('html_dir', None, "./html"),
        ('ssl', None, None),
        ('ssl_privkey', None, "ssl.key"),
        ('ssl_cert', None, "ssl.crt"),
        ('white_list', None, None,
            'Comma separated list of domains to allow connections to. \
            Begin an entry with a period to allow connections to subdomains. \
            e.g.: --white_list=.example.com,domain.com'),
        ('black_list', None, None,
         'Comma separated list of domains to deny connections to. ' \
         'Begin an entry with a period to deny connections to subdomains. '\
         'e.g.: --black_list=.example.com,domain.com'),
    ]

    optFlags = [
        ('verbose', 'v', 'Show traffic'),
    ]

class ServiceFactory(object):
    implements(IServiceMaker, IPlugin)
    tapname = "punjab"
    description = "A HTTP XMPP client interface"
    options = Options

    def makeService(self, options):
        return punjab.makeService(options)

service = ServiceFactory()

