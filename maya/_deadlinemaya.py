
import pymel.core as pc
import os
import re
import getpass
import maya.cmds as mc
import cStringIO
from abc import ABCMeta, abstractproperty, abstractmethod
from collections import OrderedDict

op = os.path


import imaya
reload(imaya)
findUIObjectByLabel = imaya.findUIObjectByLabel

from .. import deadlineWrapper as dl


class DeadlineMayaException(dl.DeadlineWrapperException):
    pass


class DeadlineMayaSubmitterBase(object):
    ''' Base class for deadline
    '''
    __metaclass__ = ABCMeta
    __removePattern__ = re.compile('[\s.;:\\/?"<>|]+')

    jobName=abstractproperty()
    comment=abstractproperty()
    department=abstractproperty()
    projectPath=abstractproperty()
    camera=abstractproperty()
    submitEachRenderLayer=abstractproperty() 
    submitEachCamera=abstractproperty()
    ignoreDefaultCamera=abstractproperty()
    strictErrorChecking=abstractproperty()
    localRendering=abstractproperty()


    def __init__(self, jobName=None, comment=None, department=None,
            projectPath=None, camera=None, repo=True):
        if jobName: self.jobName = jobName
        if comment: self.comment = comment
        if department: self.department = department
        if projectPath: self.projectPath = projectPath
        if camera: self.camera = camera

        if not dl.getStatus():
            raise DeadlineMayaException, "Deadline has negative status"

        self._repo=None
        if not repo:
            self._repo=None
        elif isinstance(repo, basestring):
            self._repo = repo
        else:
            repo = dl.getRepositoryRoot()
            if repo:
                self._repo = repo

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
        addToShelf=True
        if kwargs.has_key("addToShelf"):
            addToShelf = kwargs.pop("addToShelf")
        super(DeadlineMayaSubmitterUI, self).__init__()

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

        if not dl.getStatus():
            raise DeadlineMayaException, 'Deadline not in path'

        initScript = self.getDeadlineScript(False)

        try:
            pc.mel.source(initScript.replace("\\", "\\\\"))
            self._deadlineUIStatus = True
        except:
            self._deadlineUIStatus = False
            raise DeadlineMayaException, 'initScript Source Error'

        if addToShelf:
            self.addCustomLauncherToShelf()
        return

    def initDeadlineUI(self):
        pass

    def getDeadlineScript(self, submitScript=True):
        repo = self._repo
        if not repo:
            repo = dl.getRepositoryRoot()
        script = os.path.join(repo, "clientSetup", "Maya",
                "SubmitMayaToDeadline.mel" if submitScript else
                "InitDeadlineSubmitter.mel" )
        if os.path.exists(script):
            return script

    @staticmethod
    def _deadlineWinExists():
        return pc.window( DeadlineMayaSubmitterUI._deadlineWindowName, exists=1 )


    def addCustomLauncherToShelf(self):
        if not self._deadlineUIStatus:
            raise DeadlineMayaException, 'Deadline UI not initialized'

        command =('import ideadline.maya._deadlinemaya as deadlineSubmitter;'
                'deadlineSubmitter.DeadlineMayaSubmitterUI().openSubmissionWindow()')
        try:
            pc.uitypes.ShelfButton(self._deadlineShelfButton).setCommand(command)

        except:
            pc.shelfButton( self._deadlineShelfButton, parent=self._deadlineShelfName,
                    annotation= self._deadlineShelfButton + ": Use this one to submit",
                    image1="pythonFamily.xpm", stp="python",
                    command=command)

    def openSubmissionWindow(self, init=False, customize=True):
        if not self._deadlineUIStatus:
            raise DeadlineMayaException, 'Deadline not initialized'
        pc.mel.SubmitJobToDeadline()
        if customize:
            self.__getEditProjectButton().setCommand(pc.Callback(pc.mel.projectWindow))
            self.hideAndDisableUIElements()
            self.setJobName(DeadlineMayaSubmitterBase.buildJobName())

    def closeSubmissionWindow(self):
        if not DeadlineMayaSubmitterUI.deadlineWinExists():
            raise DeadlineMayaException, "Window does not exist"
        pc.deleteUI( self._deadlineWindowName, win=True )

    def submitRender(self, close=True):
        old_repo = None
        if self._repo:
            cur_repo = dl.getRepositoryRoot()
            if not self._repo == cur_repo:
                old_repo = cur_repo
                dl.changeRepository(self._repo)


        if not DeadlineMayaSubmitterUI._deadlineWinExists():
            raise DeadlineMayaException, "Window does not exist"
        submitButton = findUIObjectByLabel( self._deadlineWindowName,
                pc.uitypes.Button, "Submit Job")
        if not submitButton:
            raise DeadlineMayaException, "Cannot find submit Button"
        if close:
            self.closeSubmissionWindow()

        if old_repo:
            dl.changeRepository(old_repo)

    def hideAndDisableUIElements(self):
        ''' Enable disable unrelated components
        '''
        if not DeadlineMayaSubmitterUI._deadlineWinExists():
            raise DeadlineMayaException, "Window does not exist"

        pc.checkBox('frw_submitAsSuspended', e=True, v=True, en=False)

        job = findUIObjectByLabel(self._deadlineWindowName, pc.uitypes.FrameLayout,
                "Job Scheduling")
        if job:
            job.setCollapse(True)
            job.setEnable(False)

        tile = findUIObjectByLabel(self._deadlineWindowName, pc.uitypes.FrameLayout,
                "Tile Rendering")
        if tile:
            tile.setCollapse(True)
            tile.setEnable(False)

        rend = findUIObjectByLabel(self._deadlineWindowName, pc.uitypes.FrameLayout,
                "Maya Render Job")
        if rend:
            rend.setCollapse(True)
            rend.setEnable(False)

        submit = findUIObjectByLabel(self._deadlineWindowName, pc.uitypes.CheckBox,
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
        return findUIObjectByLabel('DeadlineSubmitWindow', pc.uitypes.Button, "Edit Project")

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
                raise DeadlineMayaException, "Value must be a bool"
        def getSubmitEachRenderLayer(self):
            pc.checkBox('frw_submitEachRenderLayer').getvalue()
        submitEachRenderLayer = property(fget=getSubmitEachRenderLayer,
                fset=setSubmitEachRenderLayer)

        def setSubmitEachCamera(self, value):
            if isinstance(value, bool):
                pc.checkBox('frw_submitEachCamera').setValue(value)
            else:
                raise DeadlineMayaException, "Value must be a bool"
        def getSubmitEachCamera(self):
            pc.checkBox('frw_submitEachCamera').getvalue()
        submitEachCamera = property(fget=getSubmitEachCamera,
                fset=setSubmitEachCamera)

        def setIgnoreDefaultCamera(self, value):
            if isinstance(value, bool):
                pc.checkBox('frw_ignoreDefaultCameras').setValue(value)
            else:
                raise DeadlineMayaException, "Value must be a bool"
        def getIgnoreDefaultCamera(self):
            pc.checkBox('frw_ignoreDefaultCamera').getvalue()
        ignoreDefaultCamera = property(fget=getIgnoreDefaultCamera,
                fset=setIgnoreDefaultCamera)

        def setStrictErrorChecking(self, value):
            if isinstance(value, bool):
                pc.checkBox('frw_strictErrorChecking').setValue(value)
            else:
                raise DeadlineMayaException, "Value must be a bool"
        def getStrictErrorChecking(self):
            pc.checkBox('frw_strictErrorChecking').getvalue()
        strictErrorChecking = property(fget=getStrictErrorChecking,
                fset=setStrictErrorChecking)

        def setLocalRendering(self, value):
            if isinstance(value, bool):
                pc.checkBox('frw_localRendering').setValue(value)
            else:
                raise DeadlineMayaException, "Value must be a bool"
        def getLocalRendering(self):
            pc.checkBox('frw_localRendering').getvalue()
        localRendering = property(fget=getLocalRendering,
                fset=setLocalRendering)


class DeadlineInfo(OrderedDict):
    ''' Deadline Info '''

    def toString(self):
        output = cStringIO.StringIO()
        for key, value in self.iteritems():
            print >>output, "%s=%s"%(str(key), str(value).replace('\\', '/'))
        return output.getvalue()

    def readFromString(self, fromString):
        if not isinstance(fromString, basestring):
            raise TypeError, "Only string are expected"
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
    def __init__(self, *args, **kwargs):
        super(DeadlineJobInfo, self).__init__(*args, **kwargs)
        self['Plugin']='MayaBatch'
        self['Name']=''
        self['Comment']=''
        self['Pool']='none'
        self['MachineLimit']=0
        self['Priority']=25
        self['OnJobComplete']='Nothing'
        self['TaskTimeoutMinutes']=0
        self['MinRenderTimeMinutes']=0
        self['ConcurrentTasks']=1
        self['Department']=''
        self['Group']='none'
        self['LimitGroups']=''
        self['JobDependencies']=''
        self['InitialStatus']='Active'
        self['OutputFilename0']=''
        self['Frames']='1-48'
        self['ChunkSize']='15'


class DeadlineMayaPluginInfo(DeadlineInfo):
    def __init__(self, *args, **kwargs):
        super(DeadlineMayaPluginInfo, self).__init__(*args, **kwargs)
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


class DeadlineMayaJob(object):
    ''' Submit Maya Job as rendered '''

    jobInfo = None
    pluginInfo = None
    jobId = None
    result = None
    errorString = None
    exitStatus = None
    submitOnlyOnce = True
    _repository = None
    output = None
    submitSceneFile = False

    def __init__(self, *args, **kwargs):
        self.jobInfo = DeadlineJobInfo()
        self.pluginInfo = DeadlineMayaPluginInfo()
        self.scene = mc.file(q=True, location=True)

    def setScene(self, scene):
        self.jobInfo["SceneFile"]=scene
        self.pluginInfo["SceneFile"]=scene
    def getScene(self):
        return self.pluginInfo["SceneFile"]
    scene = property(fget=getScene, fset=setScene)

    def copy(self):
        ''' Create a new object with the same values'''
        job = DeadlineMayaJob()
        job.jobInfo = self.jobInfo.copy()
        job.pluginInfo = self.jobInfo.copy()

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

    def repository():
        doc = "The repository for job submission property"
        def fget(self):
            return self._repository
        def fset(self, value):
            self._repository = value
            if not value:
                self.pluginInfo.pop('NetworkRoot')
            if value is not None:
                self.pluginInfo['NetworkRoot']=value
        return locals()
    repository = property(**repository())

    def submit(self):
        ''' submit job '''
        if self.jobId and self.submitOnlyOnce:
            raise DeadlineMayaException, ("Job Already Submitted ... try"
                    "job.copy().submit()")

            if not self.scene:
                pass

        if self.repository:
            self.pluginInfo['NetworkRoot']=self.repository

        tempdir = os.path.join(dl.getCurrentUserHomeDirectory(), "Temp")
        jobInfoFilename = os.path.join(tempdir, "deadlineJobInfo.job")
        pluginInfoFilename = os.path.join(tempdir, "mayaPluginInfo.job")

        with open(jobInfoFilename, "w") as infoFile:
            infoFile.write(self.jobInfo.toString())
        with open(pluginInfoFilename, "w") as infoFile:
            infoFile.write(self.pluginInfo.toString())

        try:
            commandargs = [jobInfoFilename, pluginInfoFilename]
            if self.submitSceneFile:
                commandargs.append(self.scene)
            self.output = dl.deadlineCommand(*commandargs)
        except dl.DeadlineWrapperException as e:
            self.output = e.message
            raise DeadlineMayaException, "Error Submitting Job\n" + e.message

        self.parseSubmissionOutput()

        return self.jobId


class DeadlineMayaSubmitter(DeadlineMayaSubmitterBase):
    _jobs=[]

    def __init__(self, jobName=None, comment=None, department=None,
            projectPath=None, camera=None, submitEachRenderLayer=None,
            submitEachCamera=None, ignoreDefaultCamera=None, outputPath=None,
            strictErrorChecking=None, localRendering=None, sceneFile=None,
            pool=None, submitAsSuspended=None, priority=None,
            submitSceneFile=None, chunkSize=None, frames=None, frameStart=None,
            frameEnd=None, frameStep=None, resolution=None):

        if jobName is None:
            self._jobName = mc.file(q=True, sceneName=True)
        else:
            self._jobName = jobName

        if comment is None:
            self._comment = ''
        else:
            self._comment = comment

        if department is None:
            self._department = ''
        else:
            self._department = department

        if projectPath is None:
            self._projectPath = imaya.getProjectPath()
        else:
            self._projectPath = projectPath

        if camera is None:
            self._camera = None
        else:
            self._camera = camera

        if submitEachRenderLayer is None:
            self._submitEachRenderLayer = 1
        else:
            self._submitEachRenderLayer = submitEachRenderLayer

        if submitEachCamera is None:
            self._submitEachCamera = 0
        else:
            self._submitEachCamera = submitEachCamera

        if ignoreDefaultCamera is None:
            self._ignoreDefaultCamera = 1
        else:
            self._ignoreDefaultCamera = ignoreDefaultCamera

        if strictErrorChecking is None:
            self._strictErrorChecking = 1
        else:
            self._strictErrorChecking = strictErrorChecking

        if sceneFile is None:
            self._sceneFile = imaya.get_file_path()
        else:
            self._sceneFile = sceneFile

        if localRendering is None:
            self._localRendering = 0
        else:
            self._localRendering = localRendering

        if localRendering is None:
            self._localRendering = 0
        else:
            self._localRendering = localRendering

        if outputPath is None:
            try:
                self._outputPath = imaya.getImagesLocation(self.projectPath)
            except RuntimeError:
                self._outputPath = op.join(self._projectPath, 'images')
        else:
            self._outputPath = outputPath

        if submitAsSuspended is None:
            self._submitAsSuspended = False
        else:
            self._submitAsSuspended = submitAsSuspended

        if priority is None:
            self._priority = '25'
        else:
            self._priority = priority

        if submitSceneFile is None:
            self._submitSceneFile = False
        else:
            self._submitSceneFile = priority

        if chunkSize is None:
            self._chunkSize=15
        else:
            self._chunkSize=chunkSize

        if pool is None:
            self._pool='none'
        else:
            self._pool=pool

        self.frameStart = frameStart
        self.frameEnd = frameEnd
        self.frameStep  = frameStep
        self.frames = frames
        self.resolution = resolution

        self._currentLayer = ''
        self._currentCamera = ''

    def configure(self):
        return True

    def createJobs(self):
        self.configure()
        self._jobs=[]
        layers = [None]
        if self.submitEachRenderLayer:
            layers = imaya.getRenderLayers()
        for layer in layers:
            try:
                imaya.setCurrentRenderLayer(layer)
            except RuntimeError:
                #fault layer ... skip
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
            raise DeadlineMayaException, (
                    'Referenced layer %s is not renderable'%str )

        job = DeadlineMayaJob()

        job.submitSceneFile = self.submitSceneFile

        layername = (layer.name() if layer.name() != "defaultRenderLayer" else
                "masterLayer")

        cameraname = camera.firstParent2() if camera else ''

        job.jobInfo['Name']=(self.jobName +
                ((" - layer - " + layername ) if self.submitEachRenderLayer
                    else '') +
                ((" - cam - "  + cameraname ) if self.submitEachCamera
                    else ''))
        job.jobInfo['Comment']=self.comment
        job.jobInfo['Pool']=self.pool
        job.jobInfo['Department']=self.department
        job.jobInfo['Priority']=self.priority
        job.jobInfo['InitialStatus']=('Suspended' if self.submitAsSuspended
                else 'Active')
        job.jobInfo['ChunkSize'] = self.chunkSize
        self.setOutputFilenames(job, layer=layer, camera=camera)
        self.setJobFrames(job)

        pi = job.pluginInfo
        pi['Animation']=int(imaya.isAnimationOn())
        pi['Renderer']=imaya.currentRenderer()
        pi['UsingRenderLayers']=1 if len(imaya.getRenderLayers(
            renderableOnly=False)) > 1 else 0
        pi['RenderLayer']=layer if layer is not None else ''
        pi['LocalRendering']=int(self.localRendering)
        pi['StrictErrorChecking']=int(self.strictErrorChecking)
        pi['Version']=imaya.maya_version()
        pi['Build']=imaya.getBitString()
        pi['ProjectPath']=op.normpath(self.projectPath).replace('\\', '/')
        pi['OutputFilePath'] = op.normpath(self.outputPath).replace('\\', '/')
        pi['OutputFilePrefix'] = imaya.getImageFilePrefix().replace('\\', '/')
        pi['Camera']=str(camera) if camera is not None else ''
        self.setJobResolution(job)
        self.setCameras(job)

        job.scene=op.normpath(self.sceneFile).replace('\\', '/')

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
            job.pluginInfo[key]=str(cam)

    def setJobFrames(self, job):
        frames = self._frames
        if frames is None:
            start, finish, step = ( self._frameStart, self._frameEnd,
                    self.frameStep )
            frameRange = imaya.getFrameRange()

            if start is None or finish is None:
                start = frameRange[0]
                finish = frameRange[1]
            if step is None:
                step = frameRange[2]

            frames = "%d-%d"%(int(start), int(finish))
            frames += 'x%d'%int(step)
        job.jobInfo['Frames']=frames

    def setOutputFilenames(self, job, layer=None, camera=None):
        '''OutputFilename0='''
        outputFilenames = imaya.getOutputFilePaths(renderLayer=layer,
                camera=camera)
        outputFilenames = [
                op.normpath(op.abspath(op.realpath(
                        op.join(self.outputPath, myfile)))).replace("\\", "/")
                if not op.isabs(myfile)
                else op.normpath(op.realpath(myfile)).replace("\\", "/")
                for myfile in outputFilenames]

        for idx, ofn in enumerate(outputFilenames):
            key = "OutputFilename" + str(idx)
            job.jobInfo[key]=ofn

    def submitJobs(self):
        for job in self._jobs:
            if not job.jobId:
                job.submit()
    submitRender = submitJobs

    def getJobs(self):
        return self._jobs

    if 'properties':
        def setJobName(self, val):
            self._jobName = val
        def getJobName(self):
            return self._jobName
        jobName=property(getJobName,setJobName)

        def setComment(self, val):
            self._comment = val
        def getComment(self):
            return self._comment
        comment=property(getComment,setComment)

        def setDepartment(self, val):
            self._department = val
        def getDepartment(self):
            return self._department
        department=property(getDepartment,setDepartment)

        def setProjectPath(self, val):
            self._projectPath = val
        def getProjectPath(self):
            return self._projectPath
        projectPath=property(getProjectPath,setProjectPath)

        def setCamera(self, val):
            self._camera = val
        def getCamera(self):
            return self._camera
        camera=property(getCamera,setCamera)

        def setSubmitEachRenderLayer(self, val):
            self._submitEachRenderLayer = val
        def getSubmitEachRenderLayer(self):
            return self._submitEachRenderLayer
        submitEachRenderLayer=property(getSubmitEachRenderLayer,setSubmitEachRenderLayer) 

        def setSubmitEachCamera(self, val):
            self._submitEachCamera = val
        def getSubmitEachCamera(self):
            return self._submitEachCamera
        submitEachCamera=property(getSubmitEachCamera,setSubmitEachCamera)

        def setIgnoreDefaultCamera(self, val):
            self._ignoreDefaultCamera = val
        def getIgnoreDefaultCamera(self):
            return self._ignoreDefaultCamera
        ignoreDefaultCamera=property(getIgnoreDefaultCamera,setIgnoreDefaultCamera)

        def setStrictErrorChecking(self, val):
            self._strictErrorChecking = val
        def getStrictErrorChecking(self):
            return self._strictErrorChecking
        strictErrorChecking=property(getStrictErrorChecking,setStrictErrorChecking)

        def setLocalRendering(self, val):
            self._localRendering = val
        def getLocalRendering(self):
            return self._localRendering
        localRendering=property(getLocalRendering,setLocalRendering)

        def setOutputPath(self, val):
            self._outputPath = val
        def getOutputPath(self):
            return self._outputPath
        outputPath=property(getOutputPath,setOutputPath)

        def setPool(self, val):
            self._pool = val
        def getPool(self):
            return self._pool
        pool=property(getPool,setPool)

        def setSceneFile(self, val):
            self._sceneFile = val
        def getSceneFile(self):
            return self._sceneFile
        sceneFile=property(getSceneFile, setSceneFile)

        def setPriority(self, val):
            if not isinstance(val, int):
                raise TypeError, 'priority must be int'
            if val < 0 or val > 100:
                raise ValueError, 'priority must be between 0 and 100'
            self._priority = val
        def getPriority(self):
            return self._priority
        priority=property(getPriority, setPriority)

        def setSubmitAsSuspended(self, val):
            val = bool(val)
            self._submitAsSuspended = val
        def getSubmitAsSuspended(self):
            return self._submitAsSuspended
        submitAsSuspended=property(getSubmitAsSuspended, setSubmitAsSuspended)

        def setSubmitSceneFile(self, val):
            self._submitAsSuspended = val
        def getSubmitSceneFile(self):
            return self._submitAsSuspended
        submitSceneFile=property(getSubmitSceneFile, setSubmitSceneFile)

        def setChunkSize(self, val):
            if not isinstance(val, int):
                raise TypeError, 'Chunk size should be an int'
            self._chunkSize = val
        def getChunkSize(self):
            return self._chunkSize
        chunkSize=property(getChunkSize, setChunkSize)

        def setFrameStart(self, val):
            self._frameStart = val
        def getFrameStart(self):
            return self._frameStart
        frameStart = property(getFrameStart, setFrameStart)

        def setFrameEnd(self, val):
            self._frameEnd = val
        def getFrameEnd(self):
            return self._frameEnd
        frameEnd = property(getFrameEnd, setFrameEnd)

        def setFrameStep(self, val):
            self._frameStep  = val
        def getFrameStep(self):
            return self._frameStep 
        frameStep  = property(getFrameStep, setFrameStep )

        def setFrames(self, val):
            self._frames = val
        def getFrames(self):
            return self._frames
        frames = property(getFrames, setFrames)

        def setResolution(self, val):
            self._resolution = val
        def getResolution(self):
            return self._resolution
        resolution = property(getResolution, setResolution)



if __name__ == '__main__':
    dui = DeadlineMayaSubmitterUI()
    dui.openSubmissionWindow()

