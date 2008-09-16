
from twisted.python import usage
import punjab

class Options(usage.Options):
    optParameters = [
        ('host', None, 'localhost'),
        ('port', None, 5280),
        ('httpb', 'b', None),
        ('polling',None,'15'),
        ('html_dir', None, "./html"),
        ('ssl',None,None),
        ('ssl_privkey',None,"ssl.key"),
        ('ssl_cert',None,"ssl.crt"),

    ]

    optFlags = [
        ('verbose', 'v', 'Show traffic'), 
    ]
    

def makeService(config):
    return punjab.makeService(config)
