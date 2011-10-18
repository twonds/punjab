from OpenSSL import SSL
from twisted.internet import ssl


# Override DefaultOpenSSLContextFactory to call ctx.use_certificate_chain_file
# instead of ctx.use_certificate_file, to allow certificate chains to be loaded.
class OpenSSLContextFactoryChaining(ssl.DefaultOpenSSLContextFactory):
    def __init__(self, *args, **kwargs):
        ssl.DefaultOpenSSLContextFactory.__init__(self, *args, **kwargs)

    def cacheContext(self):
        ctx = self._contextFactory(self.sslmethod)
        ctx.set_options(SSL.OP_NO_SSLv2)
        ctx.use_certificate_chain_file(self.certificateFileName)
        ctx.use_privatekey_file(self.privateKeyFileName)
        self._context = ctx
