import subprocess
import os
from collections import Iterable, OrderedDict
from functools import partial


import sys
sys.path.append(r"d:\talha.ahmed\workspace\repos\tactic")


import iutil
reload(iutil)


_jobFilters = [ 'getJobsFilterAnd', 'getJobsFilterIniAnd',
'getJobIdsFilter', 'getJobIdsFilterAnd', 'getJobsFilter', 'getJobsFilterIni']


__all__ = ["DeadlineWrapperException", "getStatus", "setBinPath", "getBinPath",
        "filterIitems", "deadlineCommand", "jobFilter",
        "getRepositoryRoot", "getRepositoryRoots", "cycleRepository", "changeRepository",
        "getCurrentUserHomeDirectory", "getJob", "getJobs", "getJobIds",
        ] + _jobFilters


# Constants
__deadlineCommand__ = 'DeadlineCommand'
__deadlineDefaultRepo__ = r"\\ice-sql\Deadline_5.2\DeadlineRepository"

# Setting Deadline Command path
__deadlineCmdPath__ = None
__deadlineBinPath__ = None

def getBinPath():
    return __deadlineBinPath__

def setBinPath(binPath=None):
    global __deadlineBinPath__
    global __deadlineCmdPath__
    if binPath is None:
        cmdPath = iutil.which(__deadlineCommand__)
        if cmdPath:
            __deadlineCmdPath__ = cmdPath
            __deadlineBinPath__ = os.path.dirname(cmdPath)
        else:
            __deadlineBinPath__ = os.path.join(__deadlineDefaultRepo__, "bin",
                    "Windows")
            __deadlineCmdPath__ = os.path.join(__deadlineBinPath__, __deadlineCommand__ )
    else:
        __deadlineBinPath__ = binPath
        __deadlineCmdPath__ = os.path.join(__deadlineBinPath__, __deadlineCommand__ )

setBinPath()


class DeadlineWrapperException(Exception):
    pass


def deadlineCommand(command, *args, **kwargs):
    ''' Invoke DeadlineCommand.exe to execute with the given args as commandline args'''

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

    try:
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        print commandargs
        output = subprocess.check_output(commandargs, stderr=subprocess.STDOUT,
                startupinfo=startupinfo)

    except subprocess.CalledProcessError as e:
        raise DeadlineWrapperException, ("CalledProcessError:\n" + str(e) +
                "\n\nOutput:\n" + e.output)

    return output

def getItemsFromOutput(output):
    items = []
    currentItem = OrderedDict()
    currentItem.title = None
    for line in output.splitlines():
        line = line.strip()
        if not line or line.startswith('['):
            title = line[line.find('[')+1:line.find(']')]
            if currentItem or currentItem.title:
                items.append(currentItem)
                currentItem=OrderedDict()
                currentItem.title = None
                if title:
                    currentItem.title=title
            continue

        splits = line.split('=')
        if len(splits)==1:
            items.append(line)
        elif len(splits)==2:
            currentItem[splits[0]]= splits[1]
        else:
            raise DeadlineWrapperException, 'Unexpected string format encountered'

    if currentItem or currentItem.title:
        items.append(currentItem)

    return items

matchMethods = ['eq', 'in', 'contains', 'not in', 'not contains']
def matchValue(itemval, filterval, method=matchMethods[0]):
    if method == matchMethods[0]:
        return itemval == filterval
    elif method == matchMethods[1]:
        return itemval in filterval
    elif method == matchMethods[2]:
        return filterval in itemval
    elif method == matchMethods[3]:
        return itemval not in filterval
    elif method == matchMethods[4]:
        return filterval not in itemval
    else:
        raise DeadlineWrapperException, "Unknown filter type"


def filterIitems(items, filters=[], match_any=True):
    ''' filter items on bases of the provided filters '''
    filtered = []

    for item in items:
        itemIsDict = True
        if not isinstance(item, dict):
            itemIsDict = False
        match = False
        for fil in filters:
            if isinstance(fil, basestring) or len(fil)==1:
                itemval = item
                if itemIsDict and hasattr(item, "title"):
                    itemval = item.title
                if not isinstance(fil, basestring):
                    filterval = fil[0]
                match = matchValue(itemval, filterval)
            if len(fil) == 2:
                if fil[0] in matchMethods:
                    itemval = item
                    if itemIsDict and hasattr(item, "title"):
                        itemval=item.title
                    matchValue(itemval, fil[1], fil[0])
                elif itemIsDict:
                    key, value = fil
                    match = matchValue(item.get(key), value)
            elif len(fil) == 3:
                if itemIsDict:
                    key, filtype, value = fil
                    match = matchValue(item.get(key), value, filtype)
            else:
                raise DeadlineWrapperException, "Unknown filter format"

            if (match and match_any) or not (match or match_any):
                break

        if match:
            filtered.append(item)

    return filtered


def getStatus():
    return os.path.exists(__deadlineCmdPath__)


def getRepositoryRoot():
    '''Display the repository network root '''
    return deadlineCommand("Root").strip()


def getRepositoryRoots():
    '''Display all repository roots in the Deadline config file '''
    return deadlineCommand("GetRepositoryRoots").splitlines()
networks = getRepositoryRoots

def changeRepository(repo):
    '''Display all repository roots in the Deadline config file'''
    deadlineCommand("ChangeRepository", repo)


def getCurrentUserHomeDirectory():
    '''Display all repository roots in the Deadline config file'''
    deadlineCommand("GetCurrentUserHomeDirectory").strip()


def getJobIds():
    '''Displays all the job IDs'''
    return getItemsFromOutput(deadlineCommand("GetJobIds"))


def getJobs(useIniDisplay=False):
    '''Displays information for all the jobs'''
    useIniDisplay = bool(useIniDisplay)
    return getItemsFromOutput(deadlineCommand("GetJobs", useIniDisplay))


def getJob(jobIds, useIniDisplay=False):
    '''Display information for the job'''
    useIniDisplay = bool(useIniDisplay)
    if isinstance(jobIds, basestring):
        items = getItemsFromOutput(deadlineCommand("GetJob", useIniDisplay))
        if items:
            return items[0]
    elif isinstance(jobIds, Iterable):
        return getItemsFromOutput(deadlineCommand(",".join(jobIds),
            useIniDisplay))


def cycleRepository():
    roots = getRepositoryRoots()
    if not roots:
        return
    changeRepository(roots[-1])
    return roots[-1]


def jobFilter(command, filters=[]):
    if not filters:
        raise DeadlineWrapperException, "No Filters were provided"
    filterargs = ["%s=%s"%(fil) for fil in filters]
    print filterargs
    return getItemsFromOutput(deadlineCommand(command, *filterargs))


for fil in _jobFilters:
    func = partial(jobFilter, fil)
    setattr(sys.modules[__name__], fil, func)


if __name__ == '__main__':
    print cycleRepository()

