#!/usr/bin/env python3

from collections import namedtuple

import os
import select
import signal

if not hasattr(os, "cpu_count"):
    import multiprocessing

    os.cpu_count = multiprocessing.cpu_count

from . import _support

try:
    BrokenPipeError
except NameError:
    BrokenPipeError = IOError


class JobServer:

    pass_fds = namedtuple("pass_fds", ["p2c_rd", "c2p_wr"])
    keep_fileobjs = namedtuple(
        "keep_fileobjs",
        ["c2p_rd_fileobj", "p2c_wr_fileobj", "p2c_rd_fileobj"]
    )

    def __init__(self, num_tokens=None):
        if num_tokens is None:
            num_tokens = os.cpu_count()

        self._tokens = [i for i in range(num_tokens)]

        self.poller = _support.Poller()

        # Make sure the file descriptors exist..
        self.cid2fileobjs = {}
        self.fileobj2cid = {}

        self.cid2tokens = {}
        self.token2cid = {}

        # Pipe to get signals on
        sig_rd, sig_wr = os.pipe()
        _support.set_nonblocking(sig_rd)
        _support.set_nonblocking(sig_wr)
        signal.set_wakeup_fd(sig_wr)
        self.signals = os.fdopen(sig_rd, "rb", buffering=0)
        self.fileobj2cid[self.signals] = "signal"

        self.poller.register(self.signals, select.EPOLLHUP | select.EPOLLIN)

    def _clear_logger(self):
        self._log = lambda msg: None

    def _assign_token(self, cid, token):
        self._log(
            "Child {} getting token {} (remaining: {})".format(
                cid, token, self._tokens
            )
        )
        assert token not in self.token2cid, (token, self.token2cid)
        self.token2cid[token] = cid

        assert cid in self.cid2tokens, (cid, self.cid2tokens)
        assert token not in self.cid2tokens[cid], (token, self.cid2tokens[cid])
        self.cid2tokens[cid].append(token)

        assert token in self._tokens, (token, self._tokens)
        self._tokens.remove(token)

    def _unassign_token(self, cid, token):
        self._log("Child {} returning token {}".format(cid, token))

        assert token in self.token2cid, (cid, token, self.token2cid)
        assert self.token2cid[token] == cid, (
            token, self.token2cid[token], cid
        )
        del self.token2cid[token]

        assert cid in self.cid2tokens, (cid, self.cid2tokens)
        assert token in self.cid2tokens[cid], (token, self.cid2tokens[cid])
        self.cid2tokens[cid].remove(token)

        assert token not in self._tokens
        self._tokens.append(token)

    def _add_client(self, cid, keep_fileobjs):
        """
        c2p_rd_fd = Pathway we get the tokens back from the child on.
        p2c_wr_fd = Pathway we provide tokens to the child on.

        """
        self.cid2fileobjs[cid] = keep_fileobjs

        assert keep_fileobjs.c2p_rd_fileobj not in self.fileobj2cid
        self.fileobj2cid[keep_fileobjs.c2p_rd_fileobj] = cid
        self.poller.register(
            keep_fileobjs.c2p_rd_fileobj, select.EPOLLHUP | select.EPOLLIN
        )

        assert keep_fileobjs.p2c_wr_fileobj not in self.fileobj2cid
        self.fileobj2cid[keep_fileobjs.p2c_wr_fileobj] = cid
        self.poller.register(
            keep_fileobjs.p2c_wr_fileobj, select.EPOLLHUP | select.EPOLLOUT
        )

        self.cid2tokens[cid] = []

    def _del_client(self, cid):
        assert cid in self.cid2tokens
        assert cid in self.cid2fileobjs

        in_fileobj, out_fileobj, client_fileobj = self.cid2fileobjs[cid]
        self.poller.unregister(in_fileobj)
        self.poller.unregister(out_fileobj)

        del self.cid2tokens[cid]
        del self.cid2fileobjs[cid]

    def _get_next_token(self):
        if len(self._tokens) == 0:
            return None
        else:
            return self._tokens[0]

    def tokens(self, cid):
        assert cid in self.cid2tokens
        return list(self.cid2tokens[cid])

    def create_client(self):
        c2p_rd, c2p_wr = os.pipe()
        p2c_rd, p2c_wr = os.pipe()

        # Pathway we provide tokens to the child
        p2c_wr_fileobj = os.fdopen(p2c_wr, mode="wb", buffering=0)
        # Pathway we get the tokens back from the child
        c2p_rd_fileobj = os.fdopen(c2p_rd, mode="rb", buffering=0)
        cid = c2p_rd_fileobj.fileno()

        # Copy of the p2c_rd file descriptor to allow us to read any left over
        # tokens in the pipe.
        p2c_rd_fileobj = os.fdopen(os.dup(p2c_rd), mode="rb", buffering=0)

        keep_objs = self.keep_fileobjs(
            c2p_rd_fileobj, p2c_wr_fileobj, p2c_rd_fileobj
        )
        pass_fds = self.pass_fds(p2c_rd, c2p_wr)

        self._add_client(cid, keep_objs)

        return cid, pass_fds

    def cleanup_client(self, cid, allow_tokens=False, log=None):
        if log is None:
            def _log(msg):
                pass
            log = _log

        self._log("Cleaning up {}".format(cid))
        assert cid in self.cid2tokens
        assert cid in self.cid2fileobjs

        in_fileobj, out_fileobj, client_fileobj = self.cid2fileobjs[cid]

        # Get any tokens that might be pending on the returning token pathway.
        while True:
            tokenbytes = in_fileobj.read()
            if len(tokenbytes) > 0:
                for token in tokenbytes:
                    token = self.cid2tokens[cid][0]
                    self._unassign_token(cid, token)
                continue
            assert tokenbytes == b"", repr(tokenbytes)
            in_fileobj.close()
            break

        # Open the read side of the pipe and read back anything still left in
        # it.
        out = _support.output_waiting(out_fileobj)
        out_fileobj.close()

        while out > 0:
            tokenbytes = client_fileobj.read()
            if len(tokenbytes) > 0:
                for token in tokenbytes:
                    token = self.cid2tokens[cid][0]
                    self._unassign_token(cid, token)
                continue

            assert tokenbytes == b"", repr(tokenbytes)
            break

        client_fileobj.close()

        # There should be no tokens currently left now (unless the client
        # forgot to return them...)
        current_tokens = self.cid2tokens[cid]
        assert allow_tokens or len(current_tokens) == 0, (cid, current_tokens)
        for token in current_tokens:
            self._unassign_token(cid, token)

        self._del_client(cid)

    @staticmethod
    def flags(pass_fds):
        assert isinstance(pass_fds.p2c_rd, int)
        assert isinstance(pass_fds.c2p_wr, int)
        return "-j --jobserver-fds={},{}".format(
            pass_fds.p2c_rd, pass_fds.c2p_wr
        )

    def poll(self, log=lambda msg: None, timeout=None):
        self._log = log

        for fileobj, events in self.poller.poll():
            cid = self.fileobj2cid[fileobj]
            self._log(
                "fileobj:{} cid:{} events:{}".format(fileobj, cid, events)
            )

            if cid == "signal":
                sig = fileobj.read(1)
                self._log("{} Signal {} {}".format(fileobj, events, sig))

            else:
                if "EPOLLIN" in events:
                    # Child is returning a token..
                    tokenbyte = fileobj.read(1)
                    token = self.cid2tokens[cid][0]
                    self._log(
                        "{} - Child {} return token {} ({})".format(
                            fileobj, cid, token, repr(tokenbyte)
                        )
                    )
                    self._unassign_token(cid, token)

                if "EPOLLOUT" in events:
                    out = _support.output_waiting(fileobj)
                    # Hand out a token?
                    if out > 0:
                        self._log(
                            "{} - Child already has pending tokens".format(
                                fileobj, cid, out
                            )
                        )
                        continue

                    token = self._get_next_token()
                    if token is None:
                        self._log("Unable to get token for {}".format(cid))
                        continue
                    self._assign_token(cid, token)
                    self._log(
                        "{} - Child {} given token {}".format(
                            fileobj, cid, token
                        )
                    )
                    try:
                        fileobj.write(b"+")
                    except BrokenPipeError:
                        continue

        self._clear_logger()
