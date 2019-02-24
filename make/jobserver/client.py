#!/usr/bin/env python3
"""Simple client for the make jobserver."""

import signal

from . import utils


try:
    InterruptedError = InterruptedError
except NameError:
    class InterruptedError(BaseException):
        pass


class JobServerClient:
    def __init__(self, make_flags=None):
        self.tokens = []
        job_rd_fd, job_wr_fd = utils.fds_for_jobserver(make_flags)

        self.tokens_in = job_rd_fd
        self.tokens_out = job_wr_fd

    def _sig_alarm(self, *args):
        raise InterruptedError(*args)

    def _read_with_timeout(self):
        oldhandler = signal.signal(signal.SIGALRM, self._sig_alarm)
        try:
            signal.setitimer(signal.ITIMER_REAL, 0.1)
            data = self.tokens_in.read(1)
            if len(data) == 0:
                return None
            return data
        except InterruptedError:
            return None
        finally:
            # Clear signals and then signal handlers
            # This function can actually raise a InterruptedError, if so we
            # just try the command again.
            while True:
                try:
                    signal.setitimer(signal.ITIMER_REAL, 0)
                    break
                except InterruptedError:
                    pass
            signal.signal(signal.SIGALRM, oldhandler)

    def get_token(self):
        if b"" not in self.tokens:
            # Free token
            token = b""
        else:
            # Get token from jobserver
            token = self._read_with_timeout()
            assert token is None or len(token) == 1, token

        if token is not None:
            assert isinstance(token, bytes), repr(token)
            self.tokens.append(token)

        return token

    def return_token(self, token):
        assert isinstance(token, bytes)

        if token != b"":
            # Return the token to jobserver
            self.tokens_out.write(token)

        beforelen = len(self.tokens)
        self.tokens.remove(token)
        assert beforelen - 1 == len(self.tokens)

    def cleanup(self):
        while self.tokens:
            self.return_token(self.tokens[0])

    def __str__(self):
        return "JobServer(in_tokens={}, out_tokens={})".format(
            self.tokens_in.fileno(), self.tokens_out.fileno()
        )

    def __del__(self):
        self.cleanup()
