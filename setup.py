from distutils.core import setup


setup(name='punjab',
      version='0.14',
      description='Punjab, a twisted HTTP server with interfaces to XMPP.',
      author='Christopher Zorn',
      author_email='tofu@thetofu.com',
      url='http://code.stanziq.com/punjab',
      packages=['punjab','punjab.xmpp', 'twisted.plugins'],
      package_data={'twisted.plugins': ['twisted/plugins/punjab.py']}
      )
