from distutils.core import setup

version = __import__('alda').__version__

setup(name='alda',
      version=version,
      description='ALDA',
      author='Martin Gracik',
      author_email='mgracik@redhat.com',
      url='http://',
      download_url='http://',
      license='GPLv2+',
      packages=['alda'],
      scripts=['bin/alda']
      )
