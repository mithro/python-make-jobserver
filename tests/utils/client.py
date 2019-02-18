#!/usr/bin/env python3

from __future__ import print_function

import os
import random
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from datetime import datetime

from make.jobserver import utils
from make.jobserver import client


def log(msg):
    print(
        "\n".join("{} - {}".format(os.getpid(), l) for l in msg.split("\n")),
        end="\n",
        flush=True,
    )


def main(args):
    if len(args) < 1:
        name = "client"
    else:
        name = " ".join(args[1:])

    # Should run things?
    if not utils.should_run_submake():
        return 0

    if not utils.has_jobserver():
        log("ERROR: No jobserver!")
        return -1

    log("{} - Got MAKEFLAGS: {}".format(name, utils.get_make_flags()))

    jobserver = client.JobServerClient()
    tokens = []
    log("{} - Got jobserver: {}".format(name, jobserver))

    timeout = random.randint(5, 20) / 100.0

    start_time = datetime.utcnow()
    while (datetime.utcnow() - start_time).total_seconds() < timeout:
        token = jobserver.get_token()
        if token is None:
            if len(tokens) > 5:
                break
        else:
            log(
                "{} - Got token: {} (tokens: {})".format(
                    name, repr(token), tokens
                )
            )
            tokens.append(token)

    log("{} - Got {} tokens - {}".format(name, len(tokens), tokens))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
