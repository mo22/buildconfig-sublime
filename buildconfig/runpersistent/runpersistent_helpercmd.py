from __future__ import print_function

__all__ = ['kill', 'list', 'getpid', 'open']

import os
import subprocess
import pipes

sessioncmd = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'background-process-darwin.sh')

def kill(id):
    subprocess.check_call([
        'sh',
        sessioncmd,
        'kill',
        id
    ])

def list():
    out = subprocess.check_output([
        'sh',
        sessioncmd,
        'list'
    ])
    res = []
    for i in out.strip().split("\n"):
        if i == '':
            continue
        res.append(i.split(' ', 1)[1])
    return res

def getpid(id):
    out = subprocess.check_output([
        'sh',
        sessioncmd,
        'list'
    ])
    for i in out.strip().split("\n"):
        if i == '':
            continue
        if id == i.split(' ', 1)[1]:
            return int(i.split(' ')[0])
    return None

def open(id, args, cwd=None, env=None, shell=False):
    if not cwd:
        cwd = os.getcwd()
    if not env:
        env = {}
    shell = ''
    shell += "cd %s\n" % pipes.quote(cwd)
    for (k, v) in env.items():
        shell += "export %s=%s\n" % (pipes.quote(k), pipes.quote(v))
    if shell:
        shell += ' '.join(args) + "\n"
    else:
        shell += ' '.join(pipes.quote(i) for i in args) + "\n"
    subprocess.check_call([
        'sh',
        sessioncmd,
        'open',
        id,
        shell
    ])
