
import pymel.core as pc
import os
import re
import getpass
import maya.cmds as mc
import cStringIO


from abc import ABCMeta, abstractproperty, abstractmethod
from collections import OrderedDict

import imaya
findUIObjectByLabel = imaya.findUIObjectByLabel


from . import deadlineWrapper as dl


__deadlineShelfName__ = "Thinkbox"
__deadlineShelfButton__ = "ICE_DeadlineSubmitter"

__deadlineWindowName__ = 'DeadlineSubmitWindow'

__deadlineUIStatus__ = False
__deadlineWinExists__ = lambda: pc.window(__deadlineWindowName__, exists=1)


if not dl.getStatus():
    return

__deadlineInitScript__ = os.path.join(__deadlineRepoPath__, "clientSetup",
        "Maya", "InitDeadlineSubmitter.mel")
__deadlineSubmitScript__ = os.path.join(__deadlineRepoPath__, "submission",
        "Maya", "SubmitMayaToDeadline.mel")

__removePattern__ = re.compile('[\s.;:\\/?"<>|]+')


class DeadlineMayaException(dl.DeadlineWrapperException):
    pass


class DeadlineMayaBase(object):
    ''' Base class for deadline
    '''
    __metaclass__ = ABCMeta
    __removePattern__ = re.compile('[\s.;:\\/?"<>|]+')

    jobName=abstractproperty()
    comment=abstractproperty()
    department=abstractproperty()
    projectPath=abstractproperty()
    camera=abstractproperty()

    def __init__(self, jobName=None, comment=None, department=None,
            projectPath=None, camera=None, init=True):
        if jobName: self.jobName = jobName
        if comment: self.comment = comment
        if department: self.department = department
        if projectPath: self.projectPath = projectPath
        if camera: self.camera = camera


    @classmethod
    def buildJobName(cls, project='', username='', basename=''):
        ''' buildJobName
        '''
        if not basename:
            basename = os.path.splitext(
                    os.path.basename(mc.file(q=True, sceneName=True)))[0]
        basename = cls.__removePattern__.sub( '_', basename.strip() )
        if not username:
            username = getpass.getuser()
        username = cls.__removePattern__.sub( '_', username.strip() )
        if not project:
            project="mansour_s02"
        project = cls.__removePattern__.sub( '_', project.strip() )
        return '%s__%s__%s' % (project, username, basename)

    @abstractmethod
    def submitRender():
        "submit the render job to deadline repository"
        return


class DeadlineMayaUI(DeadlineMayaBase):
    ''' Deadline Maya ui must only have one instance '''
    _instance = None

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(DeadlineMayaUI, cls).__new__(
                                cls, *args, **kwargs)
        return cls._instance

    def __init__(self, *args, **kwargs):
        addToShelf=True
        if kwargs.has_key("addToShelf"):
            addToShelf = kwargs.pop("addToShelf")
        super(DeadlineMayaUI, self).__init__()

        global __deadlineInitScript__
        global __deadlineSubmitScript__
        global __deadlineUIStatus__

        jobName = kwargs.get('jobName')
        comment = kwargs.get('comment')
        department = kwargs.get('department')
        projectPath = kwargs.get('projectPath')
        camera = kwargs.get('camera')

        if jobName: self.jobName = jobName
        if comment: self.comment = comment
        if department: self.department = department
        if projectPath: self.projectPath = projectPath
        if camera: self.camera = camera

        __deadlineInitScript__ = os.path.join(__deadlineRepoPath__,
                "clientSetup", "Maya", "InitDeadlineSubmitter.mel")
        __deadlineSubmitScript__ = os.path.join(__deadlineRepoPath__,
                "submission", "Maya", "SubmitMayaToDeadline.mel")

        if not __deadlineStatus__:
            raise DeadlineMayaException, 'Deadline not initialized'

        try:
            pc.mel.source(__deadlineInitScript__.replace("\\", "\\\\"))
            __deadlineUIStatus__ = True
        except:
            __deadlineUIStatus__ = False
            raise DeadlineMayaException, '__initScript__ Source Error'

        if addToShelf:
            self.addCustomLauncherToShelf()
        return

    def initDeadlineUI(self):
        pass

    def addCustomLauncherToShelf(self):
        if not __deadlineUIStatus__:
            raise DeadlineMayaException, 'Deadline UI not initialized'

        command =('import sceneBundle.src._deadline as deadlineSubmitter;'
                'deadlineSubmitter.DeadlineMayaUI().openSubmissionWindow()')
        try:
            pc.uitypes.ShelfButton(__deadlineShelfButton__).setCommand(command)

        except:
            pc.shelfButton( __deadlineShelfButton__, parent=__deadlineShelfName__,
                    annotation= __deadlineShelfButton__ + ": Use this one to submit",
                    image1="pythonFamily.xpm", stp="python",
                    command=command)

    def openSubmissionWindow(self, init=False, customize=True):
        if not __deadlineUIStatus__:
            raise DeadlineMayaException, 'Deadline not initialized'
        pc.mel.SubmitJobToDeadline()
        if customize:
            self.__getEditProjectButton().setCommand(pc.Callback(pc.mel.projectWindow))
            self.hideAndDisableUIElements()
            self.setJobName(DeadlineMayaBase.buildJobName())

    def closeSubmissionWindow(self):
        if not __deadlineWinExists__():
            raise DeadlineMayaException, "Window does not exist"
        pc.deleteUI( __deadlineWindowName__, win=True )

    def submitRender(self, close=True):
        if not __deadlineWinExists__():
            raise DeadlineMayaException, "Window does not exist"
        submitButton = findUIObjectByLabel( __deadlineWindowName__,
                pc.uitypes.Button, "Submit Job")
        if not submitButton:
            raise DeadlineMayaException, "Cannot find submit Button"
        if close:
            self.closeSubmissionWindow()

    def hideAndDisableUIElements(self):
        ''' Enable disable unrelated components
        '''
        if not __deadlineWinExists__():
            raise DeadlineMayaException, "Window does not exist"

        pc.checkBox('frw_submitAsSuspended', e=True, v=True, en=False)

        job = findUIObjectByLabel(__deadlineWindowName__, pc.uitypes.FrameLayout,
                "Job Scheduling")
        if job:
            job.setCollapse(True)
            job.setEnable(False)

        tile = findUIObjectByLabel(__deadlineWindowName__, pc.uitypes.FrameLayout,
                "Tile Rendering")
        if tile:
            tile.setCollapse(True)
            tile.setEnable(False)

        rend = findUIObjectByLabel(__deadlineWindowName__, pc.uitypes.FrameLayout,
                "Maya Render Job")
        if rend:
            rend.setCollapse(True)
            rend.setEnable(False)

        submit = findUIObjectByLabel(__deadlineWindowName__, pc.uitypes.CheckBox,
                "Submit Maya Scene File")
        if submit:
            submit.setEnable(False)

        pc.uitypes.OptionMenuGrp('frw_mayaBuild').setEnable(False)
        pc.uitypes.OptionMenuGrp('frw_mayaJobType').setEnable(False)
        pc.uitypes.CheckBox('frw_useMayaBatchPlugin').setEnable(False)
        pc.uitypes.IntSliderGrp('frw_FrameGroup').setValue(4)
        pc.uitypes.ColumnLayout('shotgunTabLayout').setEnable(False)

    def __getEditProjectButton(self):
        return findUIObjectByLabel('DeadlineSubmitWindow', pc.uitypes.Button, "Edit Project")

    def setJobName(self, jobname):
        pc.textFieldGrp('frw_JobName', e=True, text=jobname)
    def getJobName(self):
        return pc.textFieldGrp('frw_JobName', q=True, text=True)
    jobName = property(fget=getJobName, fset=setJobName)

    def setComment(self, comment):
        pc.textFieldGrp('frw_JobComment', e=True, text=comment)
    def getComment(self):
        pc.textFieldGrp('frw_JobComment', q=True, text=True)
    comment = property(fget=getComment, fset=setComment)

    def setDepartment(self, department):
        pc.textFieldGrp('frw_Department', e=True, text=department)
    def getDepartment(self):
        pc.textFieldGrp('frw_Department', q=True, text=True)
    department = property(fget=getDepartment, fset=setDepartment)

    def setProjectPath(self, projectpath):
        pc.textFieldGrp('frw_projectPath', e=True, text=projectpath)
    def getProjectPath(self):
        pc.textFieldGrp('frw_projectPath', q=True, text=True)
    projectPath = property(fget=getProjectPath, fset=setProjectPath)

    def setOutputPath(self, outputpath):
        pc.textFieldGrp('frw_outputFilePath', e=True, text=outputpath)
    def getOutputPath(self):
        pc.textFieldGrp('frw_outputFilePath', e=True, text=True)
    outputPath = property(fget=getOutputPath, fset=setOutputPath)

    def setCamera(self, camera):
        pc.optionMenuGrp('frw_camera').setValue
    def getCamera(self):
        pc.optionMenuGrp('frw_camera').setValue
    camera = property(fget=getCamera, fset=setCamera)


class DeadlineInfo(OrderedDict):
    def toString(self):
        output = cStringIO.StringIO()
        for key, value in self.iteritems():
            print >>output, "%s=%s"%(str(key), str(value.replace('\\', '/')))
        return output.getvalue()


class DeadlineJobInfo(DeadlineInfo):
    def __init__(self):
        super(DeadlineJobInfo, self).__init__()
        self['Plugin']='MayaBatch'
        self['Name']=''
        self['Comment']=''
        self['Pool']='none'
        self['MachineLimit']=0
        self['Priority']=50
        self['OnJobComplete']='Nothing'
        self['TaskTimeoutMinutes']=0
        self['MinRenderTimeMinutes']=0
        self['ConcurrentTasks']=1
        self['Department']=''
        self['Group']='none'
        self['LimitGroups']=''
        self['JobDependencies']=''
        self['InitialStatus']='Suspended'
        self['OutputFilename0']=''
        self['Frames']='1-48'
        self['ChunkSize']='4'


class DeadlinePluginInfo(DeadlineInfo):
    def __init__(self):
        super(DeadlinePluginInfo, self).__init__()
        self['Animation']=1
        self['Renderer']='arnold'
        self['UsingRenderLayers']=1
        self['RenderLayer']=''
        self['RenderHalfFrames']=0
        self['LocalRendering']=0
        self['StrictErrorChecking']=0
        self['MaxProcessors']=0
        self['Version']='2015'
        self['Build']='64bit'
        self['ProjectPath']=''
        self['ImageWidth']=1920
        self['ImageHeight']=1080
        self['OutputFilePath']=''
        self['OutputFilePrefix']=''
        self['Camera']=''
        self['Camera0']=''
        self['SceneFile']=''
        self['IgnoreError211']=0


class DeadlineMayaJob(DeadlineMayaBase):
    ''' Submit Maya Job as rendered '''

    jobInfo = None
    pluginInfo = None

    def __init__(self, *args, **kwargs):
        super(DeadlineMayaUI, self).__init__()
        self.jobInfo = DeadlineJobInfo()
        self.pluginInfo = DeadlinePluginInfo()

    def submitRender(self):
        pass


if __name__ == '__main__':
    dui = DeadlineMayaUI()
    dui.openSubmissionWindow()

