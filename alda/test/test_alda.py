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

import os
import unittest

import alda


# Packages.
BASESYSTEM = set([alda.Package(name='dummy-basesystem', arch=None)])
BASH = set([alda.Package(name='dummy-bash', arch=None)])


class ALDATestCase(unittest.TestCase):
    repodir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'repo')
    repodict = {'alda-repo': repodir}

    def get_alda(self, options=None, arch=None):
        alda_ = alda.ALDA(self.repodict, options)
        alda_.load_sack(arch=arch)
        return alda_


class TestDefault(ALDATestCase):

    '''
    Options:

        greedy=False,
        source=True,
        selfhosting=False,
        debuginfo=True,
        fulltree=False,
        oneatatime=False

    '''

    def setUp(self):
        self.alda = self.get_alda(arch='x86_64')

    def test_basesystem(self):
        self.alda.resolve_dependencies(BASESYSTEM)
        self.assertEqual(['dummy-basesystem-10.0-6.noarch', 'dummy-basesystem-10.0-6.src',
                          'dummy-filesystem-3-2.src', 'dummy-filesystem-3-2.x86_64',
                          'dummy-setup-2.8.48-1.noarch', 'dummy-setup-2.8.48-1.src'],
                         sorted(self.alda.installs_as_strings))

    def test_bash(self):
        self.alda.resolve_dependencies(BASH)
        self.assertEqual(['dummy-bash-4.2.24-2.src', 'dummy-bash-4.2.24-2.x86_64',
                          'dummy-bash-debuginfo-4.2.24-2.x86_64'],
                         sorted(self.alda.installs_as_strings))


class TestNoSource(ALDATestCase):

    def setUp(self):
        self.alda = self.get_alda(options=dict(source=False), arch='x86_64')

    def test_basesystem(self):
        self.alda.resolve_dependencies(BASESYSTEM)
        self.assertEqual(['dummy-basesystem-10.0-6.noarch',
                          'dummy-filesystem-3-2.x86_64',
                          'dummy-setup-2.8.48-1.noarch'],
                         sorted(self.alda.installs_as_strings))

    def test_bash(self):
        self.alda.resolve_dependencies(BASH)
        self.assertEqual(['dummy-bash-4.2.24-2.x86_64',
                          'dummy-bash-debuginfo-4.2.24-2.x86_64'],
                         sorted(self.alda.installs_as_strings))


class TestSelfHosting(ALDATestCase):

    def setUp(self):
        self.alda = self.get_alda(options=dict(selfhosting=True), arch='x86_64')

    def test_basesystem(self):
        self.alda.resolve_dependencies(BASESYSTEM)
        self.assertEqual(['dummy-basesystem-10.0-6.noarch', 'dummy-basesystem-10.0-6.src',
                          'dummy-bash-4.2.24-2.src', 'dummy-bash-4.2.24-2.x86_64',
                          'dummy-bash-debuginfo-4.2.24-2.x86_64',
                          'dummy-filesystem-3-2.src', 'dummy-filesystem-3-2.x86_64',
                          'dummy-setup-2.8.48-1.noarch', 'dummy-setup-2.8.48-1.src'],
                         sorted(self.alda.installs_as_strings))


class TestNoSourceSelfHosting(ALDATestCase):

    def setUp(self):
        self.alda = self.get_alda(options=dict(source=False, selfhosting=True), arch='x86_64')

    def test_basesystem(self):
        self.alda.resolve_dependencies(BASESYSTEM)
        self.assertEqual(['dummy-basesystem-10.0-6.noarch',
                          'dummy-bash-4.2.24-2.x86_64',
                          'dummy-bash-debuginfo-4.2.24-2.x86_64',
                          'dummy-filesystem-3-2.x86_64',
                          'dummy-setup-2.8.48-1.noarch'],
                         sorted(self.alda.installs_as_strings))


if __name__ == '__main__':
    unittest.main()
