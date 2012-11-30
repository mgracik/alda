#!/bin/bash

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

if [ $# -ne 1 ]; then
    echo "$0: missing argument"
    exit 1
fi

REPOJSON=$1
REPODIR=`dirname $1`/repo
SPECDIR=`dirname $1`/specs
TARGETS="i686 x86_64 ppc ppc64 s390 s390x"

# Exit on error.
set -e

echo "Removing old repositories"
rm -rf $REPODIR

echo "Generating spec files"
python create_spec.py $REPOJSON -d $SPECDIR

echo "Creating RPMs"
for spec in $SPECDIR/*.spec; do
    for target in $TARGETS; do
        rpmbuild --target=$target -ba --nodeps --define "_rpmdir $REPODIR" --define "_srcrpmdir $REPODIR/src" $spec
    done
done

echo "Generating repository metadata"
# for repo in $REPODIR/*; do
#     createrepo --update $repo
# done
createrepo --update $REPODIR
