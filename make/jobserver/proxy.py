#!/usr/bin/env python3

from . import server


class JobServerProxy(server.JobServer):
    def __init__(self, client):
        self.client = client
        self.token2bytes = {}
        server.JobServer.__init__(self, 0)

    def _grow_tokens(self):
        tokenbyte = self.client.get_token()
        if tokenbyte is None:
            print("Tried to _grow_tokens but get_token failed!")
            return

        tid = 0
        while tid in self.token2bytes:
            tid += 1
        assert tid not in self.token2bytes
        self.token2bytes[tid] = tokenbyte
        self._tokens.append(tid)
        print("_grow_tokens", repr(tokenbyte), tid, self._tokens)

    def _shrink_tokens(self):
        tokens = list(self._tokens)
        for tid in tokens:
            tokenbyte = self.token2bytes[tid]
            del self.token2bytes[tid]
            self.client.return_token(tid)
            self._tokens.remove(tid)
            print("_shrink_tokens", repr(tokenbyte), tid, self._tokens)

    def _get_next_token(self):
        if len(self._tokens) == 0:
            self._grow_tokens()
        return server.JobServer._get_next_token(self)

    def poll(self, log=lambda msg: None, timeout=None):
        try:
            return server.JobServer.poll(self, log, timeout)
        finally:
            if len(self._tokens) > 1:
                self._shrink_tokens()
