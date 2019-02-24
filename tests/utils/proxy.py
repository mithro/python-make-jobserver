#!/usr/bin/env python3

from __future__ import print_function

import os
import subprocess
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from make.jobserver import utils
from make.jobserver import proxy
from make.jobserver import client


def log(msg):
    print(
        "\n".join("{} - {}".format(os.getpid(), l) for l in msg.split("\n")),
        end="\n",
        flush=True,
    )


def main(args):
    proxy_retcode = int(args[1])

    # Should run things?
    if not utils.should_run_submake():
        return 0

    if not utils.has_jobserver():
        log("ERROR: No jobserver found!")
        return -1

    jobclient = client.JobServerClient()
    log("Found jobserver: {}".format(client))

    jobproxy = proxy.JobServerProxy(jobclient)
    log("Created jobserver proxy: {}".format(proxy))

    childid, pass_fds = jobproxy.create_client()

    env = dict(os.environ)
    # FIXME: This isn't quite right?
    env["MAKEFLAGS"] = utils.replace_jobserver(
        utils.get_make_flags(), jobproxy.flags(pass_fds)
    )
    cmd = " ".join(args[2:])
    log("Running '{}' with MAKEFLAGS='{}'".format(cmd, env["MAKEFLAGS"]))
    p = subprocess.Popen(args[2:], shell=False, env=env, pass_fds=pass_fds)
    for fileno in pass_fds:
        os.close(fileno)

    retcode = None
    while retcode is None:
        jobproxy.poll(timeout=0.1, log=log)
        try:
            retcode = p.wait(0.1)
        except (subprocess.TimeoutExpired, client.InterruptedError):
            pass

    log("Command '{}' finished with {}".format(cmd, retcode))
    jobproxy.poll(timeout=0.1, log=log)
    jobproxy.cleanup(log=log)
    return proxy_retcode


if __name__ == "__main__":
    sys.exit(main(sys.argv))
