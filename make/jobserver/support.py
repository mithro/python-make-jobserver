#!/usr/bin/env python3

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


def output_waiting(fileobj):
    """Return the number of bytes currently in the output buffer."""
    fd = fileobj.fileno()
    s = fcntl.ioctl(fd, termios.FIONREAD, TIOCM_zero_str)
    #s = fcntl.ioctl(fd, TIOCGSERIAL, TIOCM_zero_str)
    return struct.unpack('I', s)[0]


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

