import pymel.core as pc
import os
import re
import getpass
import maya.cmds as mc
from abc import ABCMeta, abstractproperty, abstractmethod

import imaya

from ..deadlineWrapper import (DeadlinePluginInfo, DeadlineJob,
                               DeadlineWrapperException, DeadlineAttr,
                               getStatus, getRepositoryRoot, changeRepository)

reload(imaya)
findUIObjectByLabel = imaya.findUIObjectByLabel
op = os.path


class DeadlineMayaException(DeadlineWrapperException):
    pass


class DeadlineMayaSubmitterBase(object):
    ''' Base class for deadline
    '''
    __metaclass__ = ABCMeta
    __removePattern__ = re.compile('[\s.;:\\/?"<>|]+')

    jobName = abstractproperty()
    comment = abstractproperty()
    department = abstractproperty()
    projectPath = abstractproperty()
    camera = abstractproperty()
    submitEachRenderLayer = abstractproperty()
    submitEachCamera = abstractproperty()
    ignoreDefaultCamera = abstractproperty()
    strictErrorChecking = abstractproperty()
    localRendering = abstractproperty()

    def __init__(self,
                 jobName=None,
                 comment=None,
                 department=None,
                 projectPath=None,
                 camera=None,
                 repo=True):
        if jobName:
            self.jobName = jobName
        if comment:
            self.comment = comment
        if department:
            self.department = department
        if projectPath:
            self.projectPath = projectPath
        if camera:
            self.camera = camera

        if not getStatus():
            raise DeadlineMayaException("Deadline has negative status")

        self._repo = None
        if not repo:
            self._repo = None
        elif isinstance(repo, basestring):
            self._repo = repo
        else:
            repo = getRepositoryRoot()
            if repo:
                self._repo = repo

    @classmethod
    def buildJobName(cls, project='', username='', basename=''):
        ''' buildJobName
        '''
        if not basename:
            basename = os.path.splitext(
                os.path.basename(mc.file(q=True, sceneName=True)))[0]
        basename = cls.__removePattern__.sub('_', basename.strip())
        if not username:
            username = getpass.getuser()
        username = cls.__removePattern__.sub('_', username.strip())
        if not project:
            project = "mansour_s02"
        project = cls.__removePattern__.sub('_', project.strip())
        return '%s__%s__%s' % (project, username, basename)

    @abstractmethod
    def submitRender(self):
        "submit the render job to deadline repository"
        pass

    def getRepo(self):
        return self._repo

    def setRepo(self, value):
        self._repo = value

    repo = property(getRepo, setRepo)


class DeadlineMayaSubmitterUI(DeadlineMayaSubmitterBase):
    ''' Deadline Maya ui must only have one instance '''
    _instance = None

    _deadlineShelfName = "Thinkbox"
    _deadlineShelfButton = "ICE_DeadlineSubmitter"

    _deadlineWindowName = 'DeadlineSubmitWindow'
    _deadlineUIStatus = False

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(DeadlineMayaSubmitterUI, cls).__new__(
                cls, *args, **kwargs)
        return cls._instance

    def __init__(self, *args, **kwargs):
        addToShelf = True
        if kwargs.has_key("addToShelf"):
            addToShelf = kwargs.pop("addToShelf")
        super(DeadlineMayaSubmitterUI, self).__init__()

        jobName = kwargs.get('jobName')
        comment = kwargs.get('comment')
        department = kwargs.get('department')
        projectPath = kwargs.get('projectPath')
        camera = kwargs.get('camera')

        if jobName:
            self.jobName = jobName
        if comment:
            self.comment = comment
        if department:
            self.department = department
        if projectPath:
            self.projectPath = projectPath
        if camera:
            self.camera = camera

        if not getStatus():
            raise DeadlineMayaException('Deadline not in path')

        initScript = self.getDeadlineScript(False)

        try:
            pc.mel.source(initScript.replace("\\", "\\\\"))
            self._deadlineUIStatus = True
        except:
            self._deadlineUIStatus = False
            raise DeadlineMayaException('initScript Source Error')

        if addToShelf:
            self.addCustomLauncherToShelf()
        return

    def initDeadlineUI(self):
        pass

    def getDeadlineScript(self, submitScript=True):
        repo = self._repo
        if not repo:
            repo = getRepositoryRoot()
        script = os.path.join(repo, "clientSetup", "Maya",
                              "SubmitMayaToDeadline.mel"
                              if submitScript else "InitDeadlineSubmitter.mel")
        if os.path.exists(script):
            return script

    @staticmethod
    def _deadlineWinExists():
        return pc.window(DeadlineMayaSubmitterUI._deadlineWindowName, exists=1)

    def addCustomLauncherToShelf(self):
        if not self._deadlineUIStatus:
            raise DeadlineMayaException('Deadline UI not initialized')

        command = (
            'import ideadline.maya._deadlinemaya as deadlineSubmitter;'
            'deadlineSubmitter.DeadlineMayaSubmitterUI().openSubmissionWindow()'
        )
        try:
            pc.uitypes.ShelfButton(
                self._deadlineShelfButton).setCommand(command)

        except:
            pc.shelfButton(
                self._deadlineShelfButton,
                parent=self._deadlineShelfName,
                annotation=self._deadlineShelfButton +
                ": Use this one to submit",
                image1="pythonFamily.xpm",
                stp="python",
                command=command)

    def openSubmissionWindow(self, init=False, customize=True):
        if not self._deadlineUIStatus:
            raise DeadlineMayaException('Deadline not initialized')
        pc.mel.SubmitJobToDeadline()
        if customize:
            self.__getEditProjectButton().setCommand(
                pc.Callback(pc.mel.projectWindow))
            self.hideAndDisableUIElements()
            self.setJobName(DeadlineMayaSubmitterBase.buildJobName())

    def closeSubmissionWindow(self):
        if not DeadlineMayaSubmitterUI.deadlineWinExists():
            raise DeadlineMayaException("Window does not exist")
        pc.deleteUI(self._deadlineWindowName, win=True)

    def submitRender(self, close=True):
        old_repo = None
        if self._repo:
            cur_repo = getRepositoryRoot()
            if not self._repo == cur_repo:
                old_repo = cur_repo
                changeRepository(self._repo)

        if not DeadlineMayaSubmitterUI._deadlineWinExists():
            raise DeadlineMayaException("Window does not exist")
        submitButton = findUIObjectByLabel(self._deadlineWindowName,
                                           pc.uitypes.Button, "Submit Job")
        if not submitButton:
            raise DeadlineMayaException("Cannot find submit Button")
        if close:
            self.closeSubmissionWindow()

        if old_repo:
            changeRepository(old_repo)

    def hideAndDisableUIElements(self):
        ''' Enable disable unrelated components
        '''
        if not DeadlineMayaSubmitterUI._deadlineWinExists():
            raise DeadlineMayaException("Window does not exist")

        pc.checkBox('frw_submitAsSuspended', e=True, v=True, en=False)

        job = findUIObjectByLabel(self._deadlineWindowName,
                                  pc.uitypes.FrameLayout, "Job Scheduling")
        if job:
            job.setCollapse(True)
            job.setEnable(False)

        tile = findUIObjectByLabel(self._deadlineWindowName,
                                   pc.uitypes.FrameLayout, "Tile Rendering")
        if tile:
            tile.setCollapse(True)
            tile.setEnable(False)

        rend = findUIObjectByLabel(self._deadlineWindowName,
                                   pc.uitypes.FrameLayout, "Maya Render Job")
        if rend:
            rend.setCollapse(True)
            rend.setEnable(False)

        submit = findUIObjectByLabel(self._deadlineWindowName,
                                     pc.uitypes.CheckBox,
                                     "Submit Maya Scene File")
        if submit:
            submit.setEnable(False)

        pc.uitypes.OptionMenuGrp('frw_mayaBuild').setEnable(False)
        pc.uitypes.OptionMenuGrp('frw_mayaJobType').setEnable(False)
        pc.uitypes.CheckBox('frw_useMayaBatchPlugin').setEnable(False)
        pc.uitypes.IntSliderGrp('frw_FrameGroup').setValue(4)
        pc.uitypes.ColumnLayout('shotgunTabLayout').setEnable(False)
        self.submitEachRenderLayer = True
        self.submitEachCamera = False
        self.ignoreDefaultCamera = True
        self.strictErrorChecking = True

    def __getEditProjectButton(self):
        return findUIObjectByLabel('DeadlineSubmitWindow', pc.uitypes.Button,
                                   "Edit Project")

    if 'properties':

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

        def setSubmitEachRenderLayer(self, value):
            if isinstance(value, bool):
                pc.checkBox('frw_submitEachRenderLayer').setValue(value)
            else:
                raise DeadlineMayaException("Value must be a bool")

        def getSubmitEachRenderLayer(self):
            pc.checkBox('frw_submitEachRenderLayer').getvalue()

        submitEachRenderLayer = property(
            fget=getSubmitEachRenderLayer, fset=setSubmitEachRenderLayer)

        def setSubmitEachCamera(self, value):
            if isinstance(value, bool):
                pc.checkBox('frw_submitEachCamera').setValue(value)
            else:
                raise DeadlineMayaException("Value must be a bool")

        def getSubmitEachCamera(self):
            pc.checkBox('frw_submitEachCamera').getvalue()

        submitEachCamera = property(
            fget=getSubmitEachCamera, fset=setSubmitEachCamera)

        def setIgnoreDefaultCamera(self, value):
            if isinstance(value, bool):
                pc.checkBox('frw_ignoreDefaultCameras').setValue(value)
            else:
                raise DeadlineMayaException("Value must be a bool")

        def getIgnoreDefaultCamera(self):
            pc.checkBox('frw_ignoreDefaultCamera').getvalue()

        ignoreDefaultCamera = property(
            fget=getIgnoreDefaultCamera, fset=setIgnoreDefaultCamera)

        def setStrictErrorChecking(self, value):
            if isinstance(value, bool):
                pc.checkBox('frw_strictErrorChecking').setValue(value)
            else:
                raise DeadlineMayaException("Value must be a bool")

        def getStrictErrorChecking(self):
            pc.checkBox('frw_strictErrorChecking').getvalue()

        strictErrorChecking = property(
            fget=getStrictErrorChecking, fset=setStrictErrorChecking)

        def setLocalRendering(self, value):
            if isinstance(value, bool):
                pc.checkBox('frw_localRendering').setValue(value)
            else:
                raise DeadlineMayaException("Value must be a bool")

        def getLocalRendering(self):
            pc.checkBox('frw_localRendering').getvalue()

        localRendering = property(
            fget=getLocalRendering, fset=setLocalRendering)


class DeadlineMayaPluginInfo(DeadlinePluginInfo):
    Animation = DeadlineAttr('Animation', 1, int)
    Renderer = DeadlineAttr('Renderer', 'arnold', str)
    UsingRenderLayers = DeadlineAttr('UsingRenderLayers', 1, int)
    RenderLayer = DeadlineAttr('RenderLayer', '', str)
    RenderHalfFrames = DeadlineAttr('RenderHalfFrames', 0, int)
    LocalRendering = DeadlineAttr('LocalRendering', 0, int)
    StrictErrorChecking = DeadlineAttr('StrictErrorChecking', 0, int)
    MaxProcessors = DeadlineAttr('MaxProcessors', 0, int)
    Version = DeadlineAttr('Version', '2015', str)
    Build = DeadlineAttr('Build', '64bit', str)
    ProjectPath = DeadlineAttr('ProjectPath', '', str)
    ImageWidth = DeadlineAttr('ImageWidth', 1920, int)
    ImageHeight = DeadlineAttr('ImageHeight', 1080, int)
    OutputFilePath = DeadlineAttr('OutputFilePath', '', str)
    OutputFilePrefix = DeadlineAttr('OutputFilePrefix', '', str)
    Camera = DeadlineAttr('Camera', '', str)
    Camera0 = DeadlineAttr('Camera0', '', str)
    SceneFile = DeadlineAttr('SceneFile', '', str)
    IgnoreError211 = DeadlineAttr('IgnoreError211', 0, int)


class DeadlineMayaJob(DeadlineJob):
    ''' Submit Maya Job as rendered '''

    exception = DeadlineMayaException
    pluginInfoClass = DeadlineMayaPluginInfo

    def __init__(self, *args, **kwargs):
        super(DeadlineMayaJob, self).__init__(*args, **kwargs)
        self.scene = mc.file(q=True, location=True)

    def setScene(self, scene):
        self.jobInfo["SceneFile"] = scene
        self.pluginInfo["SceneFile"] = scene

    def getScene(self):
        return self.pluginInfo["SceneFile"]

    scene = property(fget=getScene, fset=setScene)


class DeadlineSubmitterAttr(object):
    def __init__(self,
                 attr_name,
                 default=None,
                 attr_type=None,
                 range=None,
                 choices=None):
        ''':type attr_name: str'''
        if not attr_name.startswith('_'):
            attr_name = '_' + attr_name
        for char in ' .\\;,%&|<>\n\t\b':
            attr_name = attr_name.replace(char, '_')
        self.attr_name = attr_name
        self.attr_type = attr_type
        self.range = range
        self.choices = choices
        if default is None or self.checkValue(default):
            self.default = default
        else:
            self.default = None

    def checkValue(self, value):
        if self.attr_type is not None and not isinstance(
                value, self.attr_type):
            return False
        if self.choices is not None and value not in self.choices:
            return False
        if (self.range is not None and
                (value < self.range[0] or value >= self.range[1])):
            return False
        return True

    def __get__(self, instance, owner):
        if hasattr(instance, self.attr_name):
            return getattr(instance, self.attr_name)
        else:
            return self.default

    def __set__(self, instance, value):
        if value is None and self.attr_type is not None:
            value = self.default
        if self.checkValue(value):
            setattr(instance, self.attr_name, value)


class DeadlineMayaSubmitter(DeadlineMayaSubmitterBase):
    _jobs = []

    jobName = DeadlineSubmitterAttr('jobName', '', basestring)
    comment = DeadlineSubmitterAttr('comment', '', basestring)
    department = DeadlineSubmitterAttr('department', '', basestring)
    projectPath = DeadlineSubmitterAttr('projectPath', '', basestring)
    camera = DeadlineSubmitterAttr('camera', None, basestring)
    submitEachRenderLayer = DeadlineSubmitterAttr('submitEachRenderLayer', 1,
                                                  int)
    submitEachCamera = DeadlineSubmitterAttr('submitEachRenderLayer', 0, int)
    ignoreDefaultCamera = DeadlineSubmitterAttr('ignoreDefaultCamera', 0, int)
    strictErrorChecking = DeadlineSubmitterAttr('strictErrorChecking', 1, int)
    sceneFile = DeadlineSubmitterAttr('sceneFile', '', basestring)
    localRendering = DeadlineSubmitterAttr('localRendering', 0, int)
    outputPath = DeadlineSubmitterAttr('outputPath', '', basestring)
    submitAsSuspended = DeadlineSubmitterAttr('submitAsSuspended', 0, int)
    priority = DeadlineSubmitterAttr('priority', 25, int)
    submitSceneFile = DeadlineSubmitterAttr('submitSceneFile', 1, int)
    chunkSize = DeadlineSubmitterAttr('chunkSize', 15, int)
    pool = DeadlineSubmitterAttr('pool', 'none', basestring)
    secondaryPool = DeadlineSubmitterAttr('secondaryPool', '', basestring)
    frameStart = DeadlineSubmitterAttr('frameStart', None)
    frameEnd = DeadlineSubmitterAttr('frameEnd', None)
    frameStep = DeadlineSubmitterAttr('frameStep', None)
    frames = DeadlineSubmitterAttr('frames', None)
    resolution = DeadlineSubmitterAttr('resolution', None)

    def __init__(self,
                 jobName=None,
                 comment=None,
                 department=None,
                 projectPath=None,
                 camera=None,
                 submitEachRenderLayer=None,
                 submitEachCamera=None,
                 ignoreDefaultCamera=None,
                 outputPath=None,
                 strictErrorChecking=None,
                 localRendering=None,
                 sceneFile=None,
                 pool=None,
                 secondaryPool=None,
                 submitAsSuspended=None,
                 priority=None,
                 submitSceneFile=None,
                 chunkSize=None,
                 frames=None,
                 frameStart=None,
                 frameEnd=None,
                 frameStep=None,
                 resolution=None):
        if jobName is None:
            jobName = mc.file(q=True, sceneName=True)
        self.jobName = jobName
        self.comment = comment
        self.department = department
        self.projectPath = projectPath
        self.camera = camera
        self.ignoreDefaultCamera = ignoreDefaultCamera
        self.strictErrorChecking = strictErrorChecking
        if sceneFile is None:
            sceneFile = imaya.get_file_path()
        self.sceneFile = sceneFile
        self.localRendering = localRendering
        if outputPath is None:
            try:
                self.outputPath = imaya.getImagesLocation(self.projectPath)
            except RuntimeError:
                self.outputPath = op.join(self._projectPath, 'images')
        else:
            self.outputPath = outputPath
        self.submitAsSuspended = submitAsSuspended
        self.priority = priority
        self.submitSceneFile = submitSceneFile
        self.pool = pool
        self.secondaryPool = secondaryPool
        self.frameStart = frameStart
        self.frameEnd = frameEnd
        self.frameStep = frameStep
        self.frames = frames
        self.resolution = resolution

        self._currentLayer = ''
        self._currentCamera = ''

    def configure(self):
        return True

    def createJobs(self):
        self.configure()
        self._jobs = []
        layers = [None]
        if self.submitEachRenderLayer:
            layers = imaya.getRenderLayers()
        for layer in layers:
            try:
                imaya.setCurrentRenderLayer(layer)
            except RuntimeError:
                # fault layer ... skip
                continue
            self._currentLayer = layer
            camera = self.camera
            if not camera:
                # get all renderable cameras
                rencamlist = imaya.getCameras(True, False, True)
                if len(rencamlist) == 1:
                    camera = rencamlist[0]
                elif not rencamlist:
                    # give preference to 3d and added
                    rencamlist = imaya.getCameras(False, True, False)
                    if not rencamlist:
                        # dont ignore startups
                        rencamlist = imaya.getCameras(False, False, False)
                    if not rencamlist:
                        # get everything
                        rencamlist = imaya.getCamera(False, False, True)
                    camera = rencamlist[0]
            cams = [camera]
            if self.submitEachCamera:
                cams = imaya.getCameras(True, self.ignoreDefaultCamera, True)
            for cam in cams:
                self._currentCamera = cam
                if self.configure():
                    self._jobs.append(self.createJob())
        return self._jobs

    def createJob(self, layer=None, camera=None):
        '''create one job'''
        if layer is not None:
            layer = pc.nt.RenderLayer(layer)
        else:
            layer = self._currentLayer
        if camera is not None:
            camera = pc.nt.Camera(camera)
        else:
            camera = self._currentCamera

        if layer.isReferenced():
            raise DeadlineMayaException(
                'Referenced layer %s is not renderable' % str)

        job = DeadlineMayaJob()

        job.submitSceneFile = self.submitSceneFile

        layername = (layer.name() if layer.name() != "defaultRenderLayer" else
                     "masterLayer")

        cameraname = camera.firstParent2() if camera else ''

        job.jobInfo['Name'] = (self.jobName +
                               ((" - layer - " + layername)
                                if self.submitEachRenderLayer else '') +
                               ((" - cam - " + cameraname)
                                if self.submitEachCamera else ''))
        job.jobInfo['Comment'] = self.comment
        job.jobInfo['Pool'] = self.pool
        job.jobInfo['SecondaryPool'] = self.secondaryPool
        job.jobInfo['Department'] = self.department
        job.jobInfo['Priority'] = self.priority
        job.jobInfo['InitialStatus'] = ('Suspended' if self.submitAsSuspended
                                        else 'Active')
        job.jobInfo['ChunkSize'] = self.chunkSize
        self.setOutputFilenames(job, layer=layer, camera=camera)
        self.setJobFrames(job)

        pi = job.pluginInfo
        pi['Animation'] = int(imaya.isAnimationOn())
        pi['Renderer'] = imaya.currentRenderer()
        pi['UsingRenderLayers'] = 1 if len(
            imaya.getRenderLayers(renderableOnly=False)) > 1 else 0
        pi['RenderLayer'] = layer if layer is not None else ''
        pi['LocalRendering'] = int(self.localRendering)
        pi['StrictErrorChecking'] = int(self.strictErrorChecking)
        pi['Version'] = imaya.maya_version()
        pi['Build'] = imaya.getBitString()
        pi['ProjectPath'] = op.normpath(self.projectPath).replace('\\', '/')
        pi['OutputFilePath'] = op.normpath(self.outputPath).replace('\\', '/')
        pi['OutputFilePrefix'] = imaya.getImageFilePrefix().replace('\\', '/')
        pi['Camera'] = str(camera) if camera is not None else ''
        self.setJobResolution(job)
        self.setCameras(job)

        job.scene = op.normpath(self.sceneFile).replace('\\', '/')

        return job

    def setJobResolution(self, job):
        resolution = self.resolution
        if not resolution:
            resolution = imaya.getResolution()
        job.pluginInfo['ImageWidth'] = resolution[0]
        job.pluginInfo['ImageHeight'] = resolution[-1]

    def setCameras(self, job):
        cams = imaya.getCameras(False, False)
        for idx, cam in enumerate(cams):
            key = 'Camera' + str(idx + 1)
            job.pluginInfo[key] = str(cam)

    def setJobFrames(self, job):
        frames = self.frames
        if frames is None:
            start, finish, step = (self.frameStart, self.frameEnd,
                                   self.frameStep)
            frameRange = imaya.getFrameRange()

            if start is None or finish is None:
                start = frameRange[0]
                finish = frameRange[1]
            if step is None:
                step = frameRange[2]

            frames = "%d-%d" % (int(start), int(finish))
            frames += 'x%d' % int(step)
        job.jobInfo['Frames'] = frames

    def setOutputFilenames(self, job, layer=None, camera=None):
        '''OutputFilename0='''
        outputFilenames = imaya.getOutputFilePaths(
            renderLayer=layer, camera=camera)
        outputFilenames = [
            op.normpath(
                op.abspath(op.realpath(op.join(self.outputPath,
                                               myfile)))).replace("\\", "/")
            if not op.isabs(myfile) else
            op.normpath(op.realpath(myfile)).replace("\\", "/")
            for myfile in outputFilenames
        ]

        for idx, ofn in enumerate(outputFilenames):
            key = "OutputFilename" + str(idx)
            job.jobInfo[key] = ofn

    def submitJobs(self):
        jobs = []
        for job in self._jobs:
            if not job.jobId:
                job.submit()
                jobs.append(job.jobId)
        return jobs

    submitRender = submitJobs

    def getJobs(self):
        return self._jobs


if __name__ == '__main__':
    dui = DeadlineMayaSubmitterUI()
    dui.openSubmissionWindow()
