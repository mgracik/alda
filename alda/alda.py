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

from collections import namedtuple
import logging
import os
import shutil
import tempfile

import hawkey
import librepo


class Package(namedtuple('Package', 'name, arch')):

    __slots__ = ()

    def __str__(self):
        return '.'.join(self) if self.arch else self.name


class PackageSelector(object):

    def __init__(self, package, sack):
        self.package = package
        self.sack = sack
        self._query = None
        self._selector = None

    @property
    def query(self):
        if not self._query:
            query = hawkey.Query(self.sack)
            if self.package.arch:
                self._query = query.filter(name=self.package.name, arch=self.package.arch)
            else:
                self._query = query.filter(name=self.package.name)
        return self._query

    @property
    def selector(self):
        if not self._selector:
            self._selector = hawkey.Selector(self.sack)
            if self.package.arch:
                self._selector.set(name=self.package.name, arch=self.package.arch)
                self._selector.request = '%s.%s' % (self.package.name, self.package.arch)
            else:
                self._selector.set(name=self.package.name)
                self._selector.request = self.package.name
        return self._selector


class Goal(hawkey.Goal):

    def __init__(self, sack):
        super(Goal, self).__init__(sack)
        self._install_requests = set()

    def install(self, request):
        if isinstance(request, hawkey.Query):
            request.run()
            self._install_requests |= set(request.result)
            for package in request.result:
                super(Goal, self).install(package)
        elif isinstance(request, hawkey.Package):
            self._install_requests.add(request)
            super(Goal, self).install(request)
        elif isinstance(request, hawkey.Selector):
            self._install_requests.add(request.request)
            super(Goal, self).install(select=request)
        else:
            raise TypeError('Expected a Query, Package or Selector object')

    @property
    def install_requests(self):
        return list(self._install_requests)

    @property
    def install_requests_as_strings(self):
        return map(str, self.install_requests)


class Accumulator(object):

    _active_requests = []
    _max_requests = 0
    _problems = None
    _solved = None

    @staticmethod
    def update(accumulator, goal):
        if accumulator.options.get('greedy'):
            goal.run_all(accumulator.new_solution_cb)
        elif goal.run():
            accumulator.new_solution_cb(goal)
        return accumulator

    def __init__(self, options):
        self.log = logging.getLogger('alda.Accumulator')
        self.options = options
        self.sack = None
        self.query = None
        self.excludes = set()
        self.data = set()
        self._problems = set()
        self._solved = set()

    def set_sack(self, sack):
        self.sack = sack
        self.query = hawkey.Query(self.sack)

    def set_excludes(self, excludes):
        self.excludes = excludes

    def _get_srpm(self, hpo):
        if not hpo.sourcerpm:
            return []

        assert hpo.sourcerpm.endswith('.src.rpm')
        name, _version, _release = hpo.sourcerpm[:-8].rsplit('-', 2)
        query = self.query.filter(name=name, arch='src')
        query.run()
        result = filter(lambda srpm: srpm.location.endswith(hpo.sourcerpm), query.result)
        assert len(result) in (0, 1)
        return result

    def _get_debuginfo(self, hpo):
        if not hpo.sourcerpm:
            return []

        query = self.query.filter(sourcerpm=hpo.sourcerpm, name__substr='-debuginfo', arch=hpo.arch)
        query.run()
        return query.result

    def _get_subpackages(self, hpo):
        if not hpo.sourcerpm:
            return []

        query = self.query.filter(sourcerpm=hpo.sourcerpm)
        query.run()

        selectors = []
        for po in (set(query.result) - self.data):
            if po in self.skiplist:
                continue
            select = hawkey.Selector(self.sack)
            select.set(name=po.name, arch=po.arch)
            select.request = po
            selectors.append(select)
        return selectors

    def new_solution_cb(self, goal):
        # Save the new install request.
        self._active_requests.append(goal.install_requests_as_strings)
        self._max_requests = max(len(self.active_requests), self.max_requests)
        # Resolve the solution.
        self._new_solution_cb(goal)
        # Mark the request as solved.
        solved = self._active_requests.pop()
        self.log.debug('%s: request solved' % solved)
        self._solved.add(solved[0] if len(solved) == 1 else tuple(solved))

    def _new_solution_cb(self, goal):
        assert self.sack

        # Get the new packages.
        new_packages = set(goal.list_installs()) - self.data
        if not new_packages:
            self.log.debug('%s: no new packages to add', self.last_request)
            return

        # Check if some of the packages should not be excluded.
        for hpo in new_packages:
            for expo in self.excludes:
                if hpo.name == expo.name and (hpo.arch == expo.arch or expo.arch is None):
                    self.log.warning("%s: package '%s' in exclude list", self.last_request, hpo)
                    return

        # Remove the source packages if we don't want them.
        if not self.options.get('source'):
            new_packages = set(hpo for hpo in new_packages if hpo.arch != 'src')

        # Add the new packages to the set.
        self.data |= new_packages

        # Add the related packages.
        for hpo in sorted(new_packages):
            self.log.debug('added %s', hpo)

            # Source rpm.
            srpm = set(self._get_srpm(hpo)) - self.data
            if srpm:
                srpm, = srpm  # Extract the only item - this should always be a set of one.
                if self.options.get('source'):
                    self.data.add(srpm)
                    self.log.debug('added srpm %s', srpm)

                # Builddeps.
                if self.options.get('selfhosting') and srpm not in self.skiplist:
                    builddeps_goal = Goal(self.sack)
                    builddeps_goal.install(srpm)
                    builddeps_acc = self.update(self, builddeps_goal)
                    new_builddeps = builddeps_acc.data - self.data
                    self.data |= new_builddeps
                    for builddep in sorted(new_builddeps):
                        self.log.debug('added builddep %s', builddep)
                    if builddeps_goal.problems:
                        self.log.error('encountered errors when getting builddeps for %s', srpm)
                        map(self.log.error, builddeps_goal.problems)
                        self._problems.add(srpm)

            # Debuginfo.
            if self.options.get('debuginfo'):
                debuginfo = set(self._get_debuginfo(hpo)) - self.data
                if debuginfo:
                    for d in debuginfo:
                        self.data.add(d)
                        self.log.debug('added debuginfo %s', d)

            # Subpackages.
            if self.options.get('fulltree'):
                subpackages = self._get_subpackages(hpo)
                for item in subpackages:
                    subpackages_goal = Goal(self.sack)
                    subpackages_goal.install(item)
                    subpackages_acc = self.update(self, subpackages_goal)
                    new_subpackages = subpackages_acc.data - self.data
                    self.data |= new_subpackages
                    for subpackage in sorted(new_subpackages):
                        self.log.debug('added subpackage %s', subpackage)
                    if subpackages_goal.problems:
                        self.log.error('encountered errors when adding subpackage %s', item.request)
                        map(self.log.error, subpackages_goal.problems)
                        self._problems.add(item.request)

    @property
    def active_requests(self):
        return self._active_requests

    @property
    def last_request(self):
        return self.active_requests[-1]

    @property
    def max_requests(self):
        return self._max_requests

    @property
    def skiplist(self):
        return self._problems | self._solved


class ALDA(object):

    DEFAULT_OPTIONS = dict(greedy=False,
                           source=True,
                           selfhosting=False,
                           debuginfo=True,
                           fulltree=False)

    @staticmethod
    def get_repo_metadata(reponame, repopath):
        repo_handle = librepo.Handle()
        repo_result = librepo.Result()

        if repopath.startswith('/'):
            repopath = 'file://%s' % repopath

        # Set the repository URL.
        repo_handle.setopt(librepo.LRO_URL, repopath)
        if repopath.startswith('http://') or repopath.startswith('ftp://'):
            # Set the metadata destination directory.
            destdir = tempfile.mkdtemp(prefix='%s.' % reponame)
            repo_handle.setopt(librepo.LRO_DESTDIR, destdir)
        elif repopath.startswith('file://'):
            repo_handle.setopt(librepo.LRO_LOCAL, True)
            destdir = None
        else:
            raise ValueError("Incorrect repo path '%s'" % repopath)

        # Set the repository type.
        repo_handle.setopt(librepo.LRO_REPOTYPE, librepo.LR_YUMREPO)
        # Download primary.xml and filelists.xml - repomd.xml is downloaded automatically.
        repo_handle.setopt(librepo.LRO_YUMDLIST, ['primary', 'filelists'])

        repo_handle.perform(repo_result)
        return repo_result.getinfo(librepo.LRR_YUM_REPO), destdir

    @staticmethod
    def get_hawkey_repo(reponame, repoinfo):
        repo = hawkey.Repo(reponame)
        repo.repomd_fn = repoinfo['repomd']
        repo.primary_fn = repoinfo['primary']
        repo.filelists_fn = repoinfo['filelists']
        return repo

    def __init__(self, repodict, options=None):
        self.log = logging.getLogger('alda.ALDA')
        self.repodict = repodict
        self.metadirs = []
        self.options = self.DEFAULT_OPTIONS.copy()
        if options:
            self.options.update(options)

        self.sack = None
        self._installs = Accumulator(self.options)
        self._problems = set()

    def load_sack(self, arch=None, load_filelists=True, build_cache=True):
        hawkey_repos = []
        for name, path in self.repodict.items():
            self.log.info('downloading repo metadata from %s' % path)
            repoinfo, metadir = self.get_repo_metadata(reponame=name, repopath=path)
            repo = self.get_hawkey_repo(reponame=name, repoinfo=repoinfo)
            hawkey_repos.append(repo)
            self.metadirs.append(metadir) if metadir else None

        self.sack = hawkey.Sack(arch=arch) if arch else hawkey.Sack()
        for repo in hawkey_repos:
            self.sack.load_yum_repo(repo, load_filelists=load_filelists, build_cache=build_cache)
        self._installs.set_sack(self.sack)

    def resolve_dependencies(self, packages, excludes=None):
        assert self.sack

        if excludes:
            self._installs.set_excludes(excludes)

        for package in packages:
            self.log.info('resolving dependencies for %s', str(package))
            ps = PackageSelector(package, self.sack)
            if not ps.query.count():
                self.log.warning('%s: package not found', str(package))
                continue

            goal = Goal(self.sack)
            goal.install(ps.selector)
            self._installs = Accumulator.update(self._installs, goal)
            if goal.problems:
                self.log.error('encountered errors when getting dependencies for %s', str(package))
                map(self.log.error, goal.problems)
                self._problems.add(package)

        # Cleanup.
        map(shutil.rmtree, self.metadirs)

    @property
    def arches(self):
        assert self.sack
        return self.sack.list_arches()

    @property
    def installs(self):
        return list(self._installs.data)

    @property
    def installs_as_strings(self):
        return map(str, self.installs)

    @property
    def urls(self):
        return map(lambda po: os.path.join(self.repodict[po.reponame], po.location), self.installs)

    @property
    def problems(self):
        return list(self._problems)
