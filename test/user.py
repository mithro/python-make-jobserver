#!/usr/bin/env python3

import os
import random
import sys
import time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from datetime import datetime

import make


def log(msg):
    print("\n".join("{} - {}".format(os.getpid(), l) for l in msg.split('\n')), end="\n", flush=True)


def main(args):
    make_cmd = os.environ.get('MAKE', 'make')
    make_flags = os.environ.get('MAKEFLAGS', '')

    # Should run things?
    if not make.should_run_submake(make_flags):
        return 0

    if not make.has_jobserver(make_flags):
        log("ERROR: No jobserver!")
        return -1

    jobserver = make.JobServer(make_flags)
    tokens = []
    log("Got jobserver: {}".format(jobserver))

    timeout = random.randint(5, 20)

    start_time = datetime.utcnow()
    while (datetime.utcnow()-start_time).total_seconds() < timeout:
        token = jobserver.get_token()
        if token is None:
            if len(tokens) > 5:
                break
        else:
            log('Got token: {} (tokens: {})'.format(repr(token), tokens))
            tokens.append(token)

    print(os.getpid(), "Got {} tokens - {}".format(len(tokens), tokens))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
