from distutils.core import setup

setup(name='alda',
      version='0.1',
      description='ALDA',
      author='Martin Gracik',
      author_email='mgracik@redhat.com',
      url='http://',
      download_url='http://',
      license='GPLv2+',
      package_dir={'': 'src'},
      packages=['alda'],
      scripts=['src/bin/alda']
      )