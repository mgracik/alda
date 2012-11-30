# Copyright (C) 2012  Red Hat, Inc.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with this program; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
#
# Author(s):    Martin Gracik <mgracik@redhat.com>
#

import argparse
from collections import OrderedDict
import itertools
import json
import os


BODY_TAG = '__body__'
SUBPACKAGE_TAG = '__subpkg__'


def unique(seq, key=None):
    seen = set()
    if key:
        for elem in seq:
            if key(elem) not in seen:
                seen.add(key(elem))
                yield elem
    else:
        for elem in itertools.ifilterfalse(seen.__contains__, seq):
            seen.add(elem)
            yield elem


def expand(alist, prefix=''):
    if not isinstance(alist, list):
        return '%s%s' % (prefix, alist)
    else:
        s = ['%s%s' % (prefix, item) for item in alist]
        return '\n'.join(s)


class BasePackage(object):

    def __init__(self, name, header, body=None):
        self.name = name
        self.header = header
        self.body = body or {}

    @property
    def description(self):
        return self.body.get('description', self.header.get('Summary', ''))

    @property
    def prep(self):
        return self.body.get('prep', '')

    @property
    def build(self):
        return self.body.get('build', '')

    @property
    def install(self):
        install = self.body.get('install', '')
        if not install and self.files:
            dirs = unique(map(os.path.dirname, self.files))
            dirs = [os.path.normpath('%%{buildroot}/%s' % d) for d in dirs if d]
            dirs = ['mkdir -p %s' % d for d in dirs]
            files = [os.path.normpath('%%{buildroot}/%s' % f) for f in self.files]
            files = ['touch %s' % f for f in files]
            install = '\n'.join(dirs + files)
        return install

    @property
    def files(self):
        return self.body.get('files', '')


class Package(BasePackage):

    DEFAULT_HEADER = OrderedDict(Version='1.0',
                                 Release='1',
                                 License='GPLv2+')

    def __init__(self, name, header, body=None):
        # Set the header defaults.
        new_header = self.DEFAULT_HEADER.copy()
        new_header.update(header)

        super(Package, self).__init__(name, new_header, body)
        self.subpackages = []

    def render_header(self):
        s = []
        for key, value in [('Name', self.name)] + self.header.items():
            prefix = '%-16s' % (key + ':')
            s.append(expand(value, prefix))
        return '\n'.join(s)

    def render_description(self):
        return '\n%%description\n%s' % self.description

    def render_prep(self):
        return '\n%%prep\n%s' % expand(self.prep) if self.prep else ''

    def render_build(self):
        return '\n%%build\n%s' % expand(self.build) if self.build else ''

    def render_install(self):
        return '\n%%install\n%s' % expand(self.install) if self.install else ''

    def render_files(self):
        return '\n%%files\n%s' % expand(self.files)

    def add_subpackage(self, subpackage):
        self.subpackages.append(subpackage)

    def render_spec(self):
        s = []
        s.append(self.render_header())
        s.append(self.render_description())
        for sub in self.subpackages:
            s.append(sub.render_header())
            s.append(sub.render_description())
        s.append(self.render_prep())
        s.append(self.render_build())
        s.append(self.render_install())
        s.append(self.render_files())
        for sub in self.subpackages:
            s.append(sub.render_files())
        return '\n'.join(filter(None, s))

    def write_spec(self, directory=None):
        directory = directory or os.getcwd()
        if not os.path.isdir(directory):
            os.makedirs(directory)
        filename = '%s-%s-%s.spec' % (self.name, self.version, self.release)
        with open(os.path.join(directory, filename), 'w') as fileobj:
            fileobj.write(self.render_spec())
            print('Wrote: %s' % filename)

    @property
    def version(self):
        return self.header.get('Version')

    @property
    def release(self):
        return self.header.get('Release')


class SubPackage(BasePackage):

    def __init__(self, name, header, body=None):
        super(SubPackage, self).__init__(name, header, body)

    def render_header(self):
        s = ['\n%%package %s' % self.name]
        for key, value in self.header.items():
            prefix = '%-16s' % (key + ':')
            s.append(expand(value, prefix))
        return '\n'.join(s)

    def render_description(self):
        return '\n%%description %s\n%s' % (self.name, self.description)

    def render_files(self):
        return '\n%%files %s\n%s' % (self.name, self.files)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('filename')
    parser.add_argument('-d', '--directory', default=os.path.join(os.getcwd(), 'specs'))
    args = parser.parse_args()
    if not os.path.isfile(args.filename):
        raise SystemExit("File '%s' does not exist" % args.filename)

    with open(args.filename) as fileobj:
        packages = json.load(fileobj)

    for name, values in packages:
        body = values.pop(BODY_TAG, None)
        subpackages = values.pop(SUBPACKAGE_TAG, [])
        package = Package(name, values, body)
        for sub_name, sub_values in subpackages:
            sub_body = sub_values.pop(BODY_TAG, None)
            subpackage = SubPackage(sub_name, sub_values, sub_body)
            package.add_subpackage(subpackage)

        package.write_spec(args.directory)
