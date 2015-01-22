import subprocess
import os
from collections import Iterable

import site
site.addsitedir(r"d:\talha.ahmed\workspace\repos\tactic")

import iutil


__all__ = ["DeadlineWrapperException", "getStatus", "setBinPath", "getBinPath",
        "getRepositoryRoot", "getRepositoryRoots", "cycleRepository",
        "deadlineCommand"]


__deadlineCommand__ = 'DeadlineCommand'
__deadlineCmdPath__ = iutil.which(__deadlineCommand__)

__deadlineDefaultRepo__ = r"\\ice-sql\Deadline_5.2\DeadlineRepository"

if not __deadlineCmdPath__:
    __deadlineBinPath__ = os.path.normpath( os.path.join(
            __deadlineDefaultRepo__, "bin", "Windows"))
    __deadlineCmdPath__ = os.path.join(__deadlineBinPath__, __deadlineCommand__ )
else:
    __deadlineBinPath__ = os.path.dirname(__deadlineCmdPath__)

_process = None


class DeadlineWrapperException(Exception):
    pass


def deadlineCommand(command, *args, **kwargs):
    ''' Invoke DeadlineCommand.exe to execute with the given args as
    commandline args'''

    commandargs = [__deadlineCmdPath__]
    commandargs.append(command)
    commandargs.extend(args)

    for key, val in kwargs.items():
        commandargs.append("-" + key)
        if isinstance(val, basestring):
            commandargs.append(val)
        elif isinstance(val, Iterable):
            commandargs.extend(val)
        else:
            commandargs.append(str(val))

    global _process

    try:
        _process = subprocess.Popen(commandargs, stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT)
    except subprocess.CalledProcessError as e:
        raise DeadlineWrapperException, "CalledProcessError:" + str(e)

    return _process.stdout.read()


def getStatus():
    return os.path.exists(__deadlineCmdPath__)


def setBinPath(binPath):
    global __deadlineBinPath__
    global __deadlineCmdPath__
    __deadlineBinPath__ = binPath
    __deadlineCmdPath__ = os.path.join(__deadlineBinPath__, __deadlineCommand__ )


def getBinPath():
    return os.path.dirname(__deadlineCmdPath__)


def getRepositoryRoot():
    return deadlineCommand("Root").strip()


def getRepositoryRoots():
    return deadlineCommand("GetRepositoryRoots").split()


def changeRepository(repo):
    return deadlineCommand("ChangeRepository", repo)


def cycleRepository():
    roots = getRepositoryRoots()
    if not roots:
        return
    changeRepository(roots[-1])
    return roots[-1]

if __name__ == '__main__':
    print cycleRepository()

