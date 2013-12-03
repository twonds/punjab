from distutils.core import setup


# Make sure 'twisted' doesn't appear in top_level.txt

try:
    from setuptools.command import egg_info
    egg_info.write_toplevel_names
except (ImportError, AttributeError):
    pass
else:
    def _top_level_package(name):
        return name.split('.', 1)[0]

    def _hacked_write_toplevel_names(cmd, basename, filename):
        pkgs = dict.fromkeys(
            [_top_level_package(k)
                for k in cmd.distribution.iter_distribution_names()
                if _top_level_package(k) != "twisted"
            ]
        )
        cmd.write_file("top-level names", filename, '\n'.join(pkgs) + '\n')

    egg_info.write_toplevel_names = _hacked_write_toplevel_names


with open('README.txt') as file:
    long_description = file.read()

setup(name='punjab',
      version='0.15',
      description='Punjab, a twisted BOSH server.',
      long_description = long_description,
      author='Christopher Zorn',
      author_email='tofu@thetofu.com',
      zip_safe=False,
      url='https://github.com.com/twonds/punjab',
      packages=['punjab','punjab.xmpp', 'twisted.plugins'],
      package_data={'twisted.plugins': ['twisted/plugins/punjab.py']}
      )
