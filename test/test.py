#!/usr/bin/env python3

import os
import subprocess
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import make


def log(msg):
    print("\n".join("{} - {}".format(os.getpid(), l) for l in msg.split('\n')), end="\n", flush=True)


def main(args):
    make_cmd = os.environ.get('MAKE', 'make')
    make_flags = os.environ.get('MAKEFLAGS', '')
    # Should run things?
    if not make.should_run_submake(make_flags):
        return 0

    log('Current jobserver, {}'.format(make_flags))

    jobserver = make.JobServerProxy(make_flags)
    proxyid, p2c_rd, c2p_wr = jobserver.create_proxy()
    close_after_child_starts = [p2c_rd, c2p_wr]

    make_flags = make.replace_jobserver(
        make_flags, '--jobserver-fds={},{}'.format(p2c_rd, c2p_wr))
    log('New jobserver, {}'.format(make_flags))

    env = dict(os.environ)
    env['MAKEFLAGS'] = make_flags

    log('Start {} with MAKEFLAGS={}'.format(args[1:], make_flags))
    p = subprocess.Popen(
        args[1:],
        shell=False,
        close_fds=True,
        pass_fds=[0,1,2]+close_after_child_starts,
        env=env,
    )

    for fileno in close_after_child_starts:
        os.close(fileno)

    retcode = None
    while True:
        jobserver.poll(log)
        try:
            retcode = p.wait(0.1)
            if retcode is None:
                continue
            break
        except subprocess.TimeoutExpired:
            pass

    assert retcode is not None, retcode

    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
