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
            self._log(
                "Tried to _grow_tokens but get_token failed! {} {}".format(
                    repr(tokenbyte), self._tokens))

            return

        tid = 0
        while tid in self.token2bytes:
            tid += 1
        assert tid not in self.token2bytes
        self.token2bytes[tid] = tokenbyte
        self._tokens.append(tid)
        self._log("_grow_tokens {} {} {}".format(
            repr(tokenbyte), tid, self._tokens))

    def _shrink_tokens(self):
        tokens = list(self._tokens)
        for tid in tokens:
            tokenbyte = self.token2bytes[tid]
            del self.token2bytes[tid]
            self.client.return_token(tokenbyte)
            self._tokens.remove(tid)
            self._log("_shrink_tokens {} {} {}".format(
                repr(tokenbyte), tid, self._tokens))

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

    def cleanup(self, allow_tokens=True, log=lambda msg: None):
        server.JobServer.cleanup(self, allow_tokens, log)

        self._log = log
        while len(self._tokens) > 1:
            self._shrink_tokens()
        self._clear_logger()
