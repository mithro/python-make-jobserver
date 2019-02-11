#!/usr/bin/env python3

"""Simple client for the make jobserver."""

import os
import signal

from . import utils


class JobServerClient:

    def __init__(self, make_flags=None):
        self.tokens = []
        job_rd_fd, job_wr_fd = utils.fds_for_jobserver(make_flags)

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
            self.tokens.append(token)

        return token

    def return_token(self, token):
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
