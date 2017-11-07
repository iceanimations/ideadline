import subprocess
import os
from collections import Iterable, OrderedDict
from functools import partial
import re
import cStringIO
import sys

import iutil
reload(iutil)

_jobFilters = [
    'getJobsFilterAnd', 'getJobsFilterIniAnd', 'getJobIdsFilter',
    'getJobIdsFilterAnd', 'getJobsFilter', 'getJobsFilterIni'
]

__all__ = [
    "DeadlineWrapperException",
    "getStatus",
    "setBinPath",
    "getBinPath",
    "filterItems",
    "deadlineCommand",
    "jobFilter",
    "matchValue",
    "matchMethods",
    "getRepositoryRoot",
    "getRepositoryRoots",
    "cycleRepository",
    "changeRepository",
    "getCurrentUserHomeDirectory",
    "getJob",
    "getJobs",
    "getJobIds",
    "pools",
    "DeadlineAttr",
    "DeadlinePluginInfo",
    "DeadlineJobInfo",
    "DeadlineJob",
] + _jobFilters

# Constants
__deadlineCommand__ = 'DeadlineCommand'
__deadlineDefaultRepo__ = r"\\HP-011\DeadlineRepository8"
__deadlineDefaultBin__ = r'C:\Program Files\Thinkbox\Deadline8\bin'

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
            __deadlineCmdPath__ = os.path.join(__deadlineBinPath__,
                                               __deadlineCommand__)
            if not os.path.exists(__deadlineCmdPath__):
                __deadlineBinPath__ = __deadlineDefaultBin__
                __deadlineCmdPath__ = os.path.join(__deadlineBinPath__,
                                                   __deadlineCommand__)
    else:
        __deadlineBinPath__ = binPath
        __deadlineCmdPath__ = os.path.join(__deadlineBinPath__,
                                           __deadlineCommand__)


setBinPath()


class DeadlineWrapperException(Exception):
    pass


class DeadlineAttr(object):
    '''Attribute for job and plugin Info'''

    def __init__(self, key, default, attr_type=None):
        self.key = key
        self.default = default
        self.attr_type = attr_type
        self.checkValue(default)

    def checkValue(self, value):
        if self.attr_type is not None and not isinstance(
                value, self.attr_type):
            raise TypeError('value must be of type: %r' % self.attr_type)

    def __get__(self, instance, owner=None):
        ':type instance: Info'
        return instance.get(self.key, self.default)

    def __set__(self, instance, value):
        ':type instance: Info'
        self.checkValue(value)
        instance[self.key] = value


class DeadlineInfo(OrderedDict):
    ''' Deadline Info '''

    def __init__(self, *args, **kwargs):
        super(DeadlineInfo, self).__init__(*args, **kwargs)
        for val in self.__class__.__dict__.itervalues():
            if isinstance(val, DeadlineAttr) and val.key not in self:
                self[val.key] = val.default

    def toString(self):
        output = cStringIO.StringIO()
        for key, value in self.iteritems():
            print >> output, "%s=%s" % (str(key),
                                        str(value).replace('\\', '/'))
        return output.getvalue()

    def readFromString(self, fromString):
        if not isinstance(fromString, basestring):
            raise TypeError("Only string are expected")
        for line in fromString.splitlines(True):
            splits = line.split('=')
            if len(splits) < 2:
                continue
            self[splits[0]] = splits[1]

    def readFromFile(self, filename):
        with open('filename') as inputFile:
            self.readFromString(inputFile.read())

    def writeToFile(self, filename):
        with open('filename', 'w') as outputfile:
            outputfile.write(self.toString())


class DeadlineJobInfo(DeadlineInfo):
    plugin = DeadlineAttr('Plugin', 'MayaBatch', basestring)
    name = DeadlineAttr('Name', '', basestring)
    comment = DeadlineAttr('Comment', '', basestring)
    pool = DeadlineAttr('Pool', 'none', basestring)
    machineLimit = DeadlineAttr('MachineLimit', 0, int)
    priority = DeadlineAttr('Priority', 25, int)
    onJobComplete = DeadlineAttr('OnJobComplete', 'Nothing', basestring)
    taskTimeoutMinutes = DeadlineAttr('TaskTimeoutMinutes', 0, int)
    minRenderTimeoutMinutes = DeadlineAttr('MinRenderTimeMinutes', 0, int)
    concurrentTasks = DeadlineAttr('ConcurrentTasks', 1, int)
    department = DeadlineAttr('Department', '', basestring)
    group = DeadlineAttr('Group', '', basestring)
    limitGroups = DeadlineAttr('LimitGroups', '', basestring)
    jobDependencies = DeadlineAttr('JobDependencies', '', basestring)
    initialStatus = DeadlineAttr('InitialStatus', 'Active', basestring)
    outputFilename0 = DeadlineAttr('OutputFilename0', '', basestring)
    frames = DeadlineAttr('Frames', '1-48', basestring)
    chunkSize = DeadlineAttr('ChunkSize', '25', basestring)


class DeadlinePluginInfo(DeadlineInfo):
    pass


class DeadlineJob(object):
    jobInfo = None
    pluginInfo = None
    submitSceneFile = False
    jobId = None
    result = None
    errorString = None
    exitStatus = None
    submitOnlyOnce = True
    output = None
    scene = None

    pluginInfoFilename = None
    jobInfoFilename = None

    exception = DeadlineWrapperException
    pluginInfoClass = DeadlinePluginInfo

    def __init__(self,
                 jobInfo=None,
                 pluginInfo=None,
                 scene=None,
                 submitSceneFile=False,
                 submitOnlyOnce=True):
        if jobInfo is None:
            self.jobInfo = DeadlineJobInfo()
        if pluginInfo is None:
            self.pluginInfo = self.pluginInfoClass()
        self.scene = scene
        self.submitSceneFile = submitSceneFile
        self.submitOnlyOnce = submitOnlyOnce

    _repository = None

    def repository():
        doc = "The repository for job submission property"

        def fget(self):
            return self._repository

        def fset(self, value):
            self._repository = value
            if not value:
                self.pluginInfo.pop('NetworkRoot')
            if value is not None:
                self.pluginInfo['NetworkRoot'] = value

        return locals()

    repository = property(**repository())

    def copy(self):
        job = self.__class__(
            jobInfo=self.jobInfo.copy(),
            pluginInfo=self.pluginInfo.copy(),
            scene=self.scene,
            submitSceneFile=self.submitSceneFile,
            submitOnlyOnce=self.submitOnlyOnce)
        return job

    def parseSubmissionOutput(self, output=None):
        if output:
            self.output = output
        if not self.output:
            return
        output = self.output
        for line in output.splitlines(True):
            if 'exit status' in line:
                self.exitStatus = int(line.split('exit status')[-1].split()[0])
            if line.startswith('Submitting to Repository:'):
                self.repository = line.split(':')[1].strip()
            if line.startswith('Result='):
                self.result = line.split('=')[1].strip()
            if line.startswith('JobID='):
                self.jobId = line.split('=')[1].strip()
        splits = output.split("Output:")
        if len(splits) > 2:
            self.errorString = splits[-1].strip()

    def submit(self, auxFiles=None):
        ''' submit job '''
        if self.jobId and self.submitOnlyOnce:
            raise self.exception, ("Job Already Submitted ... try"
                                   "job.copy().submit()")

            if not self.scene:
                pass

        if self.repository:
            self.pluginInfo['NetworkRoot'] = self.repository

        tempdir = os.path.join(getCurrentUserHomeDirectory(), "Temp")
        self.jobInfoFilename = os.path.join(tempdir, "jobInfo.job")
        self.pluginInfoFilename = os.path.join(tempdir, "pluginInfo.job")

        with open(self.jobInfoFilename, "w") as infoFile:
            infoFile.write(self.jobInfo.toString())
        with open(self.pluginInfoFilename, "w") as infoFile:
            infoFile.write(self.pluginInfo.toString())

        try:
            commandargs = [self.jobInfoFilename, self.pluginInfoFilename]
            if self.submitSceneFile:
                commandargs.append(self.scene)
            if auxFiles:
                commandargs.extend(auxFiles)
            self.output = deadlineCommand(*commandargs)
        except DeadlineWrapperException as e:
            self.output = e.message
            raise self.exception, "Error Submitting Job\n" + e.message

        self.parseSubmissionOutput()

        return self.jobId


def deadlineCommand(command, *args, **kwargs):
    ''' Invoke DeadlineCommand.exe to execute with the given args as
    commandline args'''

    commandargs = [__deadlineCmdPath__]
    commandargs.append(command)
    commandargs.extend([str(arg) for arg in args])

    for key, val in kwargs.items():
        commandargs.append("-" + str(key))
        if isinstance(val, basestring):
            commandargs.append(val)
        elif isinstance(val, Iterable):
            commandargs.extend([str(v) for v in val])
        else:
            commandargs.append(str(val))

    try:
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        output = subprocess.check_output(
            commandargs, stderr=subprocess.STDOUT, startupinfo=startupinfo)

    except subprocess.CalledProcessError as e:
        raise DeadlineWrapperException("CalledProcessError:\n" + str(e) +
                                       "\n\nOutput:\n" + e.output)

    return output


def getItemsFromOutput(output):
    items = []
    currentItem = OrderedDict()
    currentItem.title = None
    for line in output.splitlines():
        line = line.strip()
        if not line or line.startswith('['):
            title = line[line.find('[') + 1:line.find(']')]
            if currentItem or currentItem.title:
                items.append(currentItem)
                currentItem = OrderedDict()
                currentItem.title = None
                if title:
                    currentItem.title = title
            continue

        splits = line.split('=')
        if len(splits) == 1:
            items.append(line)
        elif len(splits) == 2:
            currentItem[splits[0]] = splits[1]
        else:
            raise DeadlineWrapperException(
                'Unexpected string format encountered')

    if currentItem or currentItem.title:
        items.append(currentItem)

    return items


matchMethods = [
    'eq', 'in', 'contains', 'not in', 'not contains', 'startswith',
    'not startswith', 'endswith', 'not endswith', 'matches', 'not matches'
]


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
    elif method == matchMethods[5]:
        return itemval.startswith(filterval)
    elif method == matchMethods[6]:
        return not itemval.startswith(filterval)
    elif method == matchMethods[7]:
        return itemval.endswith(filterval)
    elif method == matchMethods[8]:
        return not itemval.endswith(filterval)
    elif method == matchMethods[9]:
        return bool(re.match(filterval, itemval))
    elif method == matchMethods[10]:
        return not bool(re.match(filterval, itemval))
    else:
        raise DeadlineWrapperException("Unknown filter type")


def filterItems(items, filters=[], match_any=True):
    ''' filter items on bases of the provided filters '''
    filtered = []

    for item in items:
        itemIsDict = True
        if not isinstance(item, dict):
            itemIsDict = False
        match = False
        for fil in filters:
            if isinstance(fil, basestring) or len(fil) == 1:
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
                        itemval = item.title
                    match = matchValue(itemval, fil[1], fil[0])
                elif itemIsDict:
                    key, value = fil
                    match = matchValue(item.get(key), value)
            elif len(fil) == 3:
                if itemIsDict:
                    key, filtype, value = fil
                    match = matchValue(item.get(key), value, filtype)
            else:
                raise DeadlineWrapperException("Unknown filter format")

            if (match and match_any) or not (match or match_any):
                break

        if match:
            filtered.append(item)

    return filtered


def getStatus():
    return os.path.exists(__deadlineCmdPath__)


def pools():
    return getItemsFromOutput(deadlineCommand("Pools"))


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
    return deadlineCommand("GetCurrentUserHomeDirectory").strip()


def executeScript(script):
    return deadlineCommand("ExecuteScript", script)


def getJobIds():
    '''Displays all the job IDs'''
    return getItemsFromOutput(deadlineCommand("GetJobIds"))


def getJobs(useIniDisplay=False):
    '''Displays information for all the jobs'''
    useIniDisplay = bool(useIniDisplay)
    return getItemsFromOutput(deadlineCommand("GetJobs", str(useIniDisplay)))


def getJob(jobIds, useIniDisplay=False):
    '''Display information for the job'''
    useIniDisplay = bool(useIniDisplay)
    if isinstance(jobIds, basestring):
        items = getItemsFromOutput(
            deadlineCommand("GetJob", str(useIniDisplay)))
        if items:
            return items[0]
    elif isinstance(jobIds, Iterable):
        return getItemsFromOutput(
            deadlineCommand(",".join(jobIds), useIniDisplay))


def cycleRepository():
    roots = getRepositoryRoots()
    if not roots:
        return
    changeRepository(roots[-1])
    return roots[-1]


def jobFilter(command, filters=[]):
    if not filters:
        raise DeadlineWrapperException, "No Filters were provided"
    filterargs = ["%s=%s" % (fil) for fil in filters]
    return getItemsFromOutput(deadlineCommand(command, *filterargs))


for fil in _jobFilters:
    func = partial(jobFilter, fil)
    setattr(sys.modules[__name__], fil, func)

if __name__ == '__main__':
    print cycleRepository()
