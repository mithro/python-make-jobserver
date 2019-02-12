#!/usr/bin/env python3

import os
import random
import subprocess
import sys
import time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from datetime import datetime

from make.jobserver import utils
from make.jobserver import server


def log(msg):
    print("\n".join("{} - {}".format(os.getpid(), l) for l in msg.split('\n')), end="\n", flush=True)


def main(args):
    # Should run things?
    if not utils.should_run_submake():
        return 0

    if utils.has_jobserver():
        log("ERROR: Jobserver already exists!")
        return -1

    jobserver = server.JobServer(num_tokens=4)
    log("Created jobserver: {}".format(jobserver))

    childid, pass_fds = jobserver.create_client()

    env = dict(os.environ)
    # FIXME: This isn't quite right?
    env['MAKEFLAGS'] = utils.get_make_flags() + jobserver.flags(pass_fds)
    cmd = ' '.join(args[1:])
    log("Running '{}' with MAKEFLAGS='{}'".format(cmd, env['MAKEFLAGS']))
    p = subprocess.Popen(
        args[1:],
        shell=False,
        env=env,
        pass_fds=pass_fds,
    )
    for fileno in pass_fds:
        os.close(fileno)

    retcode = None
    while retcode is None:
        jobserver.poll(timeout=0.1, log=log)
        try:
            retcode = p.wait(0.1)
        except subprocess.TimeoutExpired:
            pass

    log("Command '{}' finished with {}".format(cmd, retcode))

    jobserver.cleanup_client(childid)
    return retcode


if __name__ == "__main__":
    sys.exit(main(sys.argv))
