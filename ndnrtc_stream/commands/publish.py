"""publish command."""

import io
import libconf
import logging
import os
import tempfile

from .base import *
from ndnrtc_stream.commands.utils import *

logger = logging.getLogger(__name__)
ch = logging.StreamHandler(sys.stdout)
ch.setFormatter(CustomFormatter())
logger.propagate = False
logger.handlers = [ch]

sampleConfig = \
u'general = {\n\
        log_path = "";\n\
        log_level = "default";\n\
        log_file = "client.log";\n\
    };\n\
produce = {\n\
    stat_gathering = ({\n\
        name = "'+statFileId+'";\n\
        statistics = ("framesCaptured", "framesPub", "framesDrop", "segPub", "prodRate", "irecvd");\n\
    });\n\
    streams = ({\n\
        type = "video";\n\
        name = "'+streamName+'";\n\
        sync = "sound";\n\
        source = {\n\
            name = "/tmp/camera";\n\
            type = "pipe";\n\
        };\n\
        threads = ({\n\
            name = "t";\n\
        });\n\
    });\n\
};\n'

statCaptions = {'framesCaptured': 'F Captured', 'framesPub':'F Published', 'framesDrop':'F Dropped', 
                'segPub':'Seg Published', 'prodRate':'Publish Rate', 'irecvd':'Interests Recvd'}

class Publish(Base):
    def __init__(self, options, *args, **kwargs):
        Base.__init__(self, options, args, kwargs)

    def run(self):
        self.setupVideoSize()
        self.createSourcePipe()
        self.createPreviewPipe()
        self.createOverlayFile()
        self.setupProducerConfig()
        self.setupSigningIdentity()
        self.setupVerificationPolicy()

        self.ffplayProc = startFfplay(self.previewPipe, self.videoWidth, self.videoHeight, 
                                        overlayFile=self.overlayFile)
        self.ffmpegProc = startFfmpeg(self.sourcePipe, self.previewPipe, self.videoWidth, self.videoHeight)
        self.ndnrtcClientProc = startNdnrtcClient(self.configFile, self.signingIdentity, self.policyFile)
        self.childrenProcs = [self.ffplayProc, self.ffmpegProc, self.ndnrtcClientProc]
        
        dumpOutput(self.ffmpegProc.stdout, os.path.join(self.runDir, 'ffmpeg.out'))
        dumpOutput(self.ffmpegProc.stderr, os.path.join(self.runDir, 'ffmpeg.err'))
        dumpOutput(self.ffplayProc.stdout, os.path.join(self.runDir, 'ffplay.out'))
        dumpOutput(self.ffplayProc.stderr, os.path.join(self.runDir, 'ffplay.err'))
        # dumpOutput(self.ndnrtcClientProc.stdout, os.path.join(self.runDir, 'ndnrtc-client.out'))
        dumpOutput(self.ndnrtcClientProc.stderr, os.path.join(self.runDir, 'ndnrtc-client.err'))

        self.startStatWatch()

        proc = self.ndnrtcClientProc
        # proc = self.ffmpegProc
        # proc = self.ffplayProc
        try:
            while proc.poll() == None:
                line = proc.stdout.readline()
                if self.options['--verbose']:
                    sys.stdout.write(line)
        except:
            pass

        self.stopChildren()
        self.stopStatWatch()
        logger.info("completed")

    def createSourcePipe(self):
        self.sourcePipe = os.path.join(self.runDir, 'camera')
        os.mkfifo(self.sourcePipe)
        logger.debug("camera source pipe: %s"%self.sourcePipe)

    def createPreviewPipe(self):
        self.previewPipe = os.path.join(self.runDir, 'preview')
        os.mkfifo(self.previewPipe)
        logger.debug("camera preview pipe: %s"%self.previewPipe)

    def createOverlayFile(self):
        self.overlayFile = os.path.join(self.runDir, 'overlay.txt')
        with io.open(self.overlayFile, 'w') as f:
            f.write(u'-')

    def setupProducerConfig(self):
        global sampleConfig
        if self.options['--config_file']:
            self.config = libconf.load(self.options['--config_file'])
        else:
            self.config = libconf.loads(sampleConfig)
            self.config['general']['log_path'] = self.runDir
            if self.options['--verbose']:
                self.config['general']['log_level'] = 'all' 
            self.config['produce']['streams'][0]['source']['name'] = self.sourcePipe
            # customize other things, if options are available
            if self.options['--video_size']:
                logger.debug("will setup video size here")
            if self.options['--bitrate']:
                logger.debug("will setup bitrate here")
        # save config to a temp file
        self.configFile = os.path.join(self.runDir, 'producer.cfg')
        with io.open(self.configFile, mode="w") as f:
            libconf.dump(self.config, f)
        logger.debug("saved config to %s"%self.configFile)

    def setupSigningIdentity(self):
        if self.options['--identity'] or self.options['<prefix>']:
            identity = self.options['--identity'].strip() if self.options['--identity'] else self.options['<prefix>'].strip()
            res = None
            if not ndnsec_checkIdentity(identity):
                res = ndnsec_createIdentity(identity)
                if res:
                    logger.info('created self-signed identity %s'%identity)
            else:
                res = True
            if res:
                self.signingIdentity = identity
            else:
                logger.error('failed to create identity %s'%identity)
                raise Exception("failed to create identity "+identity)
        else:
            identity = ndnsec_getDefaultIdentity().strip()
            if not identity:
                logger.error('failed to acquire default identity. set default identity using ndnsec')
                raise Exception("failed to acquire default identity. Set default identity using ndnsec")
            self.signingIdentity = identity
        
        if self.options['<prefix>']:
            self.prefix = self.options['<prefix>']
        else:
            self.prefix = identity
        self.ndnrtcClientPrefix = os.path.join(self.prefix.strip(), utils.ndnrtcClientInstanceName)

        logger.info('will publish stream under %s'%self.ndnrtcClientPrefix)
        logger.info('data will be signed using %s identity'%self.signingIdentity)

    def setupVideoSize(self):
        if self.options['--video_size']:
            resolution = self.options['--video_size'].split('x')
            if len(resolution) < 2:
                logger.error('incorrect video size specified: %s. must be in a form <width>x<height>')
                raise Exception('incorrect video size specified. must be in a form <width>x<height>')
            self.videoWidth = int(resolution[0])
            self.videoHeight = int(resolution[1])
        else:
            self.videoWidth = 1280
            self.videoHeight = 720

    def setupVerificationPolicy(self):
        self.policyFile = os.path.join(self.runDir, 'policy.conf')
        with io.open(self.policyFile, 'w') as f:
            f.write(utils.samplePolicyAny)
        logger.debug('setup policy file at %s'%self.policyFile)

    def startStatWatch(self):
        global statFileId, streamName
        if not self.options['--config_file']:
            self.statFile = "%s%s-%s-%s.stat"%(statFileId, self.signingIdentity.replace('/','-'), utils.ndnrtcClientInstanceName, streamName)
            logger.debug('overlay stats are here %s'%self.statFile)
            filePath = os.path.join(self.runDir, self.statFile)
            
            def onNewLine(statLine):
                # logger.debug('new line %s and the stats are %s'%(statLine))
                overlay = "Publishing %s"%self.ndnrtcClientPrefix
                stats = statLine.split('\t')
                if len(stats) > 1:
                    idx = 1
                    for statKey in self.config['produce']['stat_gathering'][0]['statistics']:
                        try:
                            caption = statCaptions[statKey]
                            overlay += "\n%-30s %10s"%(caption, stats[idx])
                            idx += 1
                        except:
                            pass
                with open_atomic(self.overlayFile, 'w') as f:
                    f.write(overlay)

            self.statTail = Tail(filePath, onNewLine)
            self.statTail.start()

    def stopStatWatch(self):
        if self.statTail:
            self.statTail.stop()




