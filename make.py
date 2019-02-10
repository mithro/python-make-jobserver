#!/usr/bin/env python3

from datetime import datetime
import fcntl
import io
import os
import re
import select
import signal
import struct
import subprocess
import termios
import traceback


TIOCGSERIAL = getattr(termios, 'TIOCGSERIAL', 0x5411)
TIOCM_zero_str = struct.pack('I', 0)


def should_run_submake(make_flags):
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
    r = re.search(r'(?:^|\s)[^-]*(n|q)[^\s]*(\s|$)', make_flags)
    if not r:
        return True
    return not bool(r.groups()[0])


def nonblocking_fd_wrapper(blocking_fd):
    """Create a nonblocking fileobj from a blocking fileobj.

    This is needed when multiple programs are sharing a file descriptor and
    when you set the file descriptor to non-blocking the other readers will
    fail with an error like:

        read jobs pipe: Resource temporarily unavailable.  Stop.

    In theory you could use a thread for this, but they don't play nice with
    launching subprocesses (they cause random deadlocks).
    """
    read_end, write_end = os.pipe()
    if os.fork() == 0:
        # Inside the child process
        write_end = os.fdopen(write_end, 'wb')
        try:
            while True:
                byte = blocking_fd.read(1)
                if len(data) == 0:
                    break
                write_end.write(byte)
        finally:
            blocking_fd.close()
            write_end.close()
            sys.exit(0)

    # Continuing in the parent process
    read_end = os.fdopen(write_end, 'rb')
    set_nonblocking(read_end)
    return read_end


JOBSERVER_REGEX = '--jobserver-fds=([0-9]+),([0-9]+)'


def has_jobserver(make_flags):
    return '--jobserver' in make_flags


def replace_jobserver(make_flags, new_jobserver):
    if not has_jobserver(make_flags):
        return make_flags
    else:
        new_make_flags = re.sub(JOBSERVER_REGEX, new_jobserver, make_flags)
        assert new_jobserver in new_make_flags, (make_flags, new_jobserver, new_make_flags)
        return new_make_flags



def set_nonblocking(fileobj):
    if isinstance(fileobj, int):
        fd = fileobj
    else:
        fd = fileobj.fileno()
    fl = fcntl.fcntl(fd, fcntl.F_GETFL)
    fcntl.fcntl(fd, fcntl.F_SETFL, fl | os.O_NONBLOCK)

def set_blocking(fileobj):
    if isinstance(fileobj, int):
        fd = fileobj
    else:
        fd = fileobj.fileno()
    fl = fcntl.fcntl(fd, fcntl.F_GETFL)
    fcntl.fcntl(fd, fcntl.F_SETFL, fl & ~os.O_NONBLOCK)


class JobServer:

    @staticmethod
    def jobserver_fds(make_flags):
        if not has_jobserver(make_flags):
            return None, None

        # Play nice with make's jobserver.
        # See https://www.gnu.org/software/make/manual/html_node/POSIX-Jobserver.html#POSIX-Jobserver  # noqa
        job_re = re.search(JOBSERVER_REGEX, make_flags)
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

    def __init__(self, make_flags):
        self.tokens = []
        job_rd_fd, job_wr_fd = self.jobserver_fds(make_flags)

        self.tokens_in = job_rd_fd
        self.tokens_out = job_wr_fd

        signal.signal(signal.SIGALRM, self._sig_alarm)

    def _sig_alarm(self, *args):
        raise InterruptedError(*args)

    def _read_with_timeout(self):
        try:
            signal.setitimer(signal.ITIMER_REAL, 0.1)
            return self.tokens_in.read(1)
        except InterruptedError:
            return None

    def get_token(self):
        if b'' not in self.tokens:
            # Free token
            token = b''
        else:
            # Get token from jobserver
            token = self._read_with_timeout()
            assert token is None or len(token) == 1, token

        if token is not None:
            assert isinstance(token, bytes), repr(token)
            print(os.getpid(), "get_token:", repr(token), self.tokens)
            self.tokens.append(token)

        return token

    def return_token(self, token):
        print(os.getpid(), "return_token:", repr(token), self.tokens)
        assert isinstance(token, bytes)

        if token != b'':
            # Return the token to jobserver
            self.tokens_out.write(token)

        beforelen = len(self.tokens)
        self.tokens.remove(token)
        assert beforelen-1 == len(self.tokens)

    def cleanup(self):
        while self.tokens:
            self.return_token(self.tokens[0])

    def __str__(self):
        return 'JobServer(in_tokens={}, out_tokens={})'.format(
            self.tokens_in.fileno(),
            self.tokens_out.fileno(),
        )

    def __del__(self):
        self.cleanup()


class JobServerProxy:

    @staticmethod
    def _out_waiting(fileobj):
        """Return the number of bytes currently in the output buffer."""
        fd = fileobj.fileno()
        s = fcntl.ioctl(fd, termios.FIONREAD, TIOCM_zero_str)
        #s = fcntl.ioctl(fd, TIOCGSERIAL, TIOCM_zero_str)
        return struct.unpack('I', s)[0]

    def __init__(self, make_flags):
        self.poller = Poller()

        # Make sure the file descriptors exist..
        self.proxyid2fileobj = {}
        self.fileobj2proxyid = {}

        self.proxyid2tokens = {}

        self.jobserver = JobServer(make_flags)

        self.fileobj2proxyid[self.jobserver.tokens_in] = 'parent'
        self.poller.register(self.jobserver.tokens_in, select.EPOLLHUP | select.EPOLLIN)

        #self.fileobj2proxyid[self.jobserver.tokens_out] = 'parent'
        #self.poller.register(self.jobserver.tokens_out, select.EPOLLHUP)

        #sig_rd, sig_wr = os.pipe()
        #set_nonblocking(sig_rd)
        #set_nonblocking(sig_wr)
        #signal.set_wakeup_fd(sig_wr)
        #self.signals = os.fdopen(sig_rd, 'rb', buffering=0)
        #self.fileobj2proxyid[self.signals] = 'signal'
        #self.poller.register(self.signals, select.EPOLLHUP | select.EPOLLIN)

    def _add_proxy(self, proxyid, c2p_rd_fd, p2c_wr_fd):
        """

        c2p_rd_fd = Pathway we get the tokens back from the child on.
        p2c_wr_fd = Pathway we provide tokens to the child on.

        """
        assert p2c_wr_fd
        assert c2p_rd_fd

        self.proxyid2fileobj[proxyid] = (c2p_rd_fd, p2c_wr_fd)

        assert c2p_rd_fd not in self.fileobj2proxyid
        self.fileobj2proxyid[c2p_rd_fd] = proxyid
        #self.poller.register(c2p_rd_fd, select.EPOLLHUP | select.EPOLLIN)

        assert p2c_wr_fd not in self.fileobj2proxyid
        self.fileobj2proxyid[p2c_wr_fd] = proxyid
        #self.poller.register(p2c_wr_fd, select.EPOLLHUP | select.EPOLLOUT)

        self.proxyid2tokens = []

    def create_proxy(self):
        c2p_rd, c2p_wr = os.pipe()
        p2c_rd, p2c_wr = os.pipe()

        # Pathway we provide tokens to the child
        p2c_wr_fd = os.fdopen(p2c_wr, mode='wb', buffering=0)
        # Pathway we get the tokens back from the child
        c2p_rd_fd = os.fdopen(c2p_rd, mode='rb', buffering=0)

        proxyid = c2p_rd_fd.fileno()

        self._add_proxy(proxyid, c2p_rd_fd, p2c_wr_fd)
        return proxyid, p2c_rd, c2p_wr

    def poll(self, log):
        for fileobj, events in self.poller.poll():
            proxyid = self.fileobj2proxyid[fileobj]
            log('fileobj:{} proxyid:{} events:{}'.format(fileobj, proxyid, events))
            if proxyid == 'parent':
                log('{} Parent {}'.format(fileobj, events))

            elif proxyid == 'signal':
                sig = fileobj.read(1)
                log('{} Signal {} {}'.format(fileobj, events, sig))

            else:
                if 'EPOLLIN' in events:
                    # Child is returning a token..
                    token = fileobj.read(1)
                    log('{} - Child {} return token {}'.format(fileobj, proxyid, repr(token)))
                    self.proxyid2tokens.remove(token)

                if 'EPOLLOUT' in events:
                    out = self._out_waiting(fileobj)
                    # Hand out a token?
                    if out > 0:
                        log(fileobj, proxyid, events, out)
                        continue

                    token = self.jobserver.get_token()
                    if token is None:
                        log('Unable to get token from {}'.format(self.jobserver))
                        continue
                    self.proxyid2tokens.append(token)
                    log('{} - Giving child {} token {}'.format(fileobj, proxyid, repr(token)))
                    fileobj.write(token)


def run_make(target, directory, logdir, log, jobserver=None):

    time_start = datetime.utcnow()

    log_suffix = ".{}.log".format(time_start.isoformat())
    stdout = os.path.join(logdir, "stdout" + log_suffix)
    stderr = os.path.join(logdir, "stderr" + log_suffix)

    make_cmd = os.environ.get('MAKE', 'make')
    make_flags = os.environ.get('MAKEFLAGS', '')

    close_after_child_starts = []
    if not has_jobserver(make_flags):
        assert jobserver is None, (make_flags, jobserver)

    elif jobserver is not None:
        proxyid, p2c_rd, c2p_wr = jobserver.create_proxy()

        close_after_child_starts.append(p2c_rd)
        close_after_child_starts.append(c2p_wr)

        make_flags = replace_jobserver(
            make_flags, '--jobserver-fds={},{}'.format(p2c_rd, c2p_wr))
        log('New jobserver, {}'.format(make_flags))

    else:
        # Make sure not to close the fds as make uses fd=(3,4) for process
        # control.
        p2c_rd, c2p_wr = jobserver_fds(make_flags)

    start_msg = "Starting @ {}".format(time_start.isoformat())
    running_msg = "Running {} -C {} {} (with MAKEFLAGS='{}')".format(
        make_cmd,
        directory,
        target,
        make_flags,
    )
    log("{}\n{}".format(start_msg, running_msg))

    # Write header to stdout/stderr to make sure they match.
    for fname in [stdout, stderr]:
        with open(fname, "w") as fd:
            fd.write(start_msg)
            fd.write("\n")
            fd.write(running_msg)
            fd.write("\n")
            fd.write("-" * 75)
            fd.write("\n")
            fd.flush()
            os.fsync(fd)

    # Open the log files for appending
    stdout_fd = open(stdout, "a")
    stderr_fd = open(stderr, "a")

    close_after_child_starts.append(stdout_fd)
    close_after_child_starts.append(stderr_fd)

    env = dict(os.environ)
    env['MAKEFLAGS'] = make_flags

    retcode = None
    try:
        p = subprocess.Popen(
            [make_cmd, '-C', directory, target],
            shell=False,
            stdin=None,
            #stdout=stdout_fd,
            #stderr=stderr_fd,
            env=env,
        )

        for fileno in close_after_child_starts:
            os.close(fileno)

        while True:
            if jobserver:
                jobserver.poll(log)
            try:
                retcode = p.wait(timeout=1)
                p = None
            except subprocess.TimeoutExpired:
                log("Still waiting on {}".format(p.pid))
                retcode = None

            if retcode is not None:
                break

    except (Exception, KeyboardInterrupt, SystemExit):
        retcode = -1
        tb = io.StringIO()
        traceback.print_exc(file=tb)

    return retcode


EPOLL_NAMES = {
    select.EPOLLIN: 'EPOLLIN',
    select.EPOLLOUT:           'EPOLLOUT',
    select.EPOLLPRI:           'EPOLLPRI',
    select.EPOLLERR:           'EPOLLERR',
    select.EPOLLHUP:           'EPOLLHUP',
    select.EPOLLET:            'EPOLLET',
    select.EPOLLONESHOT:       'EPOLLONESHOT',
#    select.EPOLLEXCLUSIVE:    'EPOLLEXCLUSIVE',
#    select.EPOLLRDHUP:         'EPOLLRDHUP',
    select.EPOLLRDNORM:        'EPOLLRDNORM',
    select.EPOLLRDBAND:        'EPOLLRDBAND',
    select.EPOLLWRNORM:        'EPOLLWRNORM',
    select.EPOLLWRBAND:        'EPOLLWRBAND',
    select.EPOLLMSG:           'EPOLLMSG',
}


class Poller:
    def __init__(self):
        self.epoll = select.epoll()
        self.mapping = {}

    def register(self, fileobj, flags):
        assert fileobj.fileno() not in self.mapping, (fileobj.fileno(), fileobj, self.mapping)
        self.mapping[fileobj.fileno()] = fileobj

        if select.EPOLLIN & flags:
            assert 'r' in fileobj.mode, fileobj
        if select.EPOLLOUT & flags:
            assert 'w' in fileobj.mode, fileobj

        self.epoll.register(fileobj, flags)

    def poll(self, *args, **kw):
        for fileno, event in self.epoll.poll(*args, **kw):

            events = []
            for v, name in EPOLL_NAMES.items():
                if event & v:
                    events.append(name)
            assert events, event
            assert fileno in self.mapping
            yield self.mapping[fileno], events
