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
        ('host', None, 'localhost', "The hostname sent in the HTTP header of BOSH requests"),
        ('port', None, 5280, "HTTP Port for BOSH connections"),
        ('httpb', 'b', "http-bind", "URL path for BOSH resource."),
        ('polling', None, '15', "Seconds allowed between client polling requests"),
        ('html_dir', None, "./html", "The path were static html files are served."),
        ('ssl', None, None, "A flag to turn on ssl for BOSH requests"),
        ('ssl_privkey', None, "ssl.key", "SSL private key location"),
        ('ssl_cert', None, "ssl.crt", "SSL certificate location"),
        ('white_list', None, None,
            'Comma separated list of domains to allow connections to. \
            Begin an entry with a period to allow connections to subdomains. \
            e.g.: --white_list=.example.com,domain.com'),
        ('black_list', None, None,
         'Comma separated list of domains to deny connections to. ' \
         'Begin an entry with a period to deny connections to subdomains. '\
         'e.g.: --black_list=.example.com,domain.com'),
        ('site_log_file', None, None,
         'File path where the site access logs will be written. ' \
         'This overrides the twisted default logging. ' \
         'e.g.: --site_log_file=/var/log/punjab.access.log'),
    ]

    optFlags = [
        ('verbose', 'v', 'Show traffic and verbose logging.'),
    ]

class ServiceFactory(object):
    implements(IServiceMaker, IPlugin)
    tapname = "punjab"
    description = "A HTTP XMPP client interface"
    options = Options

    def makeService(self, options):
        return punjab.makeService(options)

service = ServiceFactory()

