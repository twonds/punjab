"""
Punjab - multiple http interfaces to jabber.

"""

from twisted.application import service
from twisted.application import strports
from twisted.python import log

from . import session


class PunjabService(service.MultiService):
    """Punjab parent service"""

    httpb = None

    def startService(self):
        return service.MultiService.startService(self)

    def stopService(self):
        def cb(result):
            return service.MultiService.stopService(self)

        d = self.httpb.stopService()
        d.addCallback(cb).addErrback(log.err)
        return d


class Service(service.Service):
    """
    Punjab generice service
    """

    def error(self, failure, body=None):
        """
        A Punjab error has occurred
        """
        # need a better way to trap this
        if failure.getErrorMessage() != 'remote-stream-error':
            log.msg('Punjab Error: ')
            log.msg(failure.printBriefTraceback())
            log.msg(body)
        failure.raiseException()

    def success(self, result, body=None):
        """
        If success we log it and return result
        """
        log.msg(body)
        return result


def makeService(config):
    """
    Create a punjab service to run
    """
    from twisted.web import server, resource, static
    from twisted.application import internet

    from . import httpb

    serviceCollection = PunjabService()

    if config['html_dir']:
        r = static.File(config['html_dir'])
    else:
        print("The html directory is needed.")
        return

    if config['white_list']:
        httpb.HttpbService.white_list = config['white_list'].split(',')

    if config['black_list']:
        httpb.HttpbService.black_list = config['black_list'].split(',')

    if config['httpb']:
        b = httpb.HttpbService(config['verbose'], config['polling'])
        if config['httpb'] == '':
            r.putChild(b'http-bind', resource.IResource(b))
        else:
            r.putChild(config['httpb'].encode('utf-8'), resource.IResource(b))

    if config['route']:
        httpb.HttpbService.route = 'xmpp:'+config['route']

    if config['site_log_file']:
        site = server.Site(r, logPath=config['site_log_file'])
    else:
        site = server.Site(r)

    session.DIRECT_TLS = bool(config.get('directTLS'))

    if config['strports']:
        for strport in config['strports']:
            sm = strports.service(
                strport,
                site,
            )
            sm.setServiceParent(serviceCollection)
    elif config['ssl']:
        from OpenSSL import SSL
        from punjab.ssl import OpenSSLContextFactoryChaining
        ssl_context = OpenSSLContextFactoryChaining(config['ssl_privkey'],
                                                    config['ssl_cert'],
                                                    SSL.SSLv23_METHOD,)
        sm = internet.SSLServer(int(config['port']),
                                site,
                                ssl_context,
                                backlog=int(config['verbose']))
        sm.setServiceParent(serviceCollection)
    else:
        sm = internet.TCPServer(int(config['port']), site)

        sm.setServiceParent(serviceCollection)

    serviceCollection.httpb = b
    return serviceCollection
