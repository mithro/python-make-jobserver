#!/usr/bin/env python3

"""Helpful utils for working with Make's jobserver."""

import os
import re


def get_make(make=None):
    if make_flags is None:
        make_flags = os.environ.get('MAKE', 'make')
    assert isinstance(make_flags, str), repr(make_flags)
    return make_flags


def get_make_flags(make_flags=None):
    if make_flags is None:
        make_flags = os.environ.get('MAKEFLAGS', '')
    assert isinstance(make_flags, str), repr(make_flags)
    return make_flags


def should_run_submake(make_flags=None):
    """Check if make_flags indicate that we should execute things.

    See https://www.gnu.org/software/make/manual/html_node/Instead-of-Execution.html#Instead-of-Execution  # noqa

    If this is a dry run or question then we shouldn't execute or output
    anything.

    The flags end up as single letter versions in the MAKEFLAGS environment
    variable.

    >>> should_run_submake('')
    True

    The following flags are important;

     -n == --dry-run

    >>> should_run_submake('n')
    False
    >>> should_run_submake('n --blah')
    False
    >>> should_run_submake('--blah n')
    False
    >>> should_run_submake('--blah')
    True
    >>> should_run_submake('--random')
    True

     -q == --question

    >>> should_run_submake('q')
    False
    >>> should_run_submake('q --blah')
    False
    >>> should_run_submake('--blah q')
    False
    >>> should_run_submake('--blah')
    True
    >>> should_run_submake('--random')
    True

      Both --dry-run and --question

    >>> should_run_submake('qn')
    False
    >>> should_run_submake('nq')
    False
    >>> should_run_submake('--quiant')
    True
    """
    make_flags = get_make_flags(make_flags)

    r = re.search(r'(?:^|\s)[^-]*(n|q)[^\s]*(\s|$)', make_flags)
    if not r:
        return True
    return not bool(r.groups()[0])


_JOBSERVER_REGEX = '--jobserver-fds=([0-9]+),([0-9]+)'


def has_jobserver(make_flags=None):
    make_flags = get_make_flags(make_flags)
    return '--jobserver' in make_flags


def replace_jobserver(make_flags, new_jobserver):
    """

    >>> replace_jobserver(
    ...     "random --jobserver-fds=4,5 stuff",
    ...     "--jobserver-fds=6,7",
    ... )
    "random --jobserver-fds=6,7 stuff"

    """
    if not has_jobserver(make_flags):
        return make_flags
    else:
        new_make_flags = re.sub(_JOBSERVER_REGEX, new_jobserver, make_flags)
        assert new_jobserver in new_make_flags, (make_flags, new_jobserver, new_make_flags)
        return new_make_flags


def fds_for_jobserver(make_flags=None):
    if not has_jobserver(make_flags):
        return None, None

    job_re = re.search(_JOBSERVER_REGEX, make_flags)
    assert job_re, make_flags
    job_rd, job_wr = job_re.groups()

    job_rd = int(job_rd)
    job_wr = int(job_wr)
    assert job_rd > 2, (job_rd, job_wr, make_flags)
    assert job_wr > 2, (job_rd, job_wr, make_flags)

    # Make sure the file descriptors exist..
    job_rd_fd = os.fdopen(int(job_rd), 'rb', 0)
    assert job_rd_fd
    job_wr_fd = os.fdopen(int(job_wr), 'wb', 0)
    assert job_wr_fd
    return job_rd_fd, job_wr_fd
