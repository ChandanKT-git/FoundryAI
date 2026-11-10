"""Runs a command as an unprivileged throwaway uid with no network, resource limits and a scrubbed env.
Usage: python sandbox_launch.py <uid> <workdir> <cmd...>"""
import errno
import json
import os
import resource
import socket
import sys

import pyseccomp as sc


def main():
    uid, workdir, cmd = int(sys.argv[1]), sys.argv[2], sys.argv[3:]
    cpu = int(os.environ.get("SANDBOX_CPU", "90"))
    extra = json.loads(os.environ.get("SANDBOX_ENV", "{}"))
    resource.setrlimit(resource.RLIMIT_CPU, (cpu, cpu))
    if os.environ.get("SANDBOX_MEM"):
        mem = int(os.environ["SANDBOX_MEM"])
        resource.setrlimit(resource.RLIMIT_AS, (mem, mem))
    resource.setrlimit(resource.RLIMIT_FSIZE, (50 * 2**20, 50 * 2**20))
    resource.setrlimit(resource.RLIMIT_NPROC, (128, 128))
    resource.setrlimit(resource.RLIMIT_NOFILE, (256, 256))
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    os.setgroups([])
    os.setgid(uid)
    os.setuid(uid)
    os.chdir(workdir)
    f = sc.SyscallFilter(defaction=sc.ALLOW)
    deny = sc.ERRNO(errno.EACCES)
    f.add_rule(deny, "socket", sc.Arg(0, sc.NE, socket.AF_UNIX))  # no TCP/UDP/raw/netlink
    for name in ("connect", "io_uring_setup", "ptrace", "process_vm_readv", "process_vm_writev", "bpf",
                 "mount", "umount2", "unshare", "setns", "keyctl", "add_key", "request_key"):
        f.add_rule(deny, name)
    f.load()  # sets no_new_privs, so the filter and uid cannot be undone
    os.execvpe(cmd[0], cmd, {
        "PATH": "/usr/local/bin:/usr/bin:/bin", "HOME": workdir, "LANG": "C.UTF-8",
        "PYTHONPATH": os.environ.get("SANDBOX_PYTHONPATH", ""), "PYTHONDONTWRITEBYTECODE": "1",
        "NODE_OPTIONS": "--max-old-space-size=384", "CI": "1", **extra,
    })


if __name__ == "__main__":
    main()
