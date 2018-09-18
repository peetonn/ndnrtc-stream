"""fetch command."""

import io
import libconf
import logging
import os
import tempfile

from .base import *
from json import dumps
from ndnrtc_stream.commands.utils import *

logger = logging.getLogger(__name__)
ch = logging.StreamHandler(sys.stdout)
ch.setFormatter(CustomFormatter())
logger.propagate = False
logger.handlers = [ch]

sampleConfig= \
u'general = {\n\
        log_path="";\n\
        log_level = "default";\n\
        log_file = "client.log";\n\
    };\n\
consume = {\n\
    basic = {\n\
        stat_gathering = ({\n\
            name = "'+statFileId+'";\n\
            statistics= ("isent", "segNumRcvd", "appNacks", "nacks", "timeouts", "rtxNum",\
            "bytesRcvd", "rawBytesRcvd", "lambdaD", "drdEst", "jitterPlay",\
            "framesReq", "framesPlayed", "framesInc", "skipNoKey");\n\
        });\n\
    };\n\
    streams = ({\n\
        type = "video";\n\
        base_prefix = "";\n\
        name = "camera";\n\
        thread_to_fetch = "t";\n\
        sink = {\n\
            name = "";\n\
            type = "pipe";\n\
            write_frame_info = false;\n\
        }\n\
    });\n\
};\n'

statCaptions = {'isent': 'Interests sent', 'segNumRcvd': 'Segments Rcvd', 'appNacks': 'App Nacks', 'nacks': 'Netw Nacks', 'timeouts':'Timeouts', 'rtxNum':'RTX',
                'bytesRcvd': 'Bytes Rcvd', 'rawBytesRcvd':'Bytes Rcvd (raw)', 'lambdaD': 'Pipeline', 'drdEst': 'DRD (ms)', 'jitterPlay':'Buffer size (ms)',
                'framesReq': 'F Requested', 'framesPlayed': 'F Played', 'framesInc': 'F Incomplete', 'skipNoKey': 'F Skipped'}

class Fetch(Base):
    def __init__(self, options, *args, **kwargs):
        Base.__init__(self, options, args, kwargs)

    def run(self):
        self.setupConsumerConfig()
        self.setupSigningIdentity()
        self.setupVerificationPolicy()
        self.setupPreviewPipe()
        self.createOverlayFile()

        self.ffplayProc = startFfplay(self.previewPipe, self.videoWidth, self.videoHeight, self.overlayFile)
        self.ndnrtcClientProc = startNdnrtcClient(self.configFile, self.signingIdentity, self.policyFile)
        self.childrenProcs = [self.ndnrtcClientProc, self.ffplayProc]
        self.startStatWatch()

        dumpOutput(self.ffplayProc.stdout, os.path.join(self.runDir, 'ffplay.out'))
        dumpOutput(self.ffplayProc.stderr, os.path.join(self.runDir, 'ffplay.err'))
        dumpOutput(self.ndnrtcClientProc.stderr, os.path.join(self.runDir, 'ndnrtc-client.err'))

        logger.info('fetching from %s'%self.basePrefix)
        proc = self.ndnrtcClientProc
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

    def setupConsumerConfig(self):
        global sampleConfig
        if self.options['--config_file']:
            self.config = libconf.load(self.options['--config_file'])
        else:
            self.config = libconf.loads(sampleConfig)
            self.config['general']['log_path'] = self.runDir
            if self.options['--verbose']:
                self.config['general']['log_level'] = 'all' 
            streamPrefix = self.options['<stream_prefix>']
            self.basePrefix = streamPrefix if streamPrefix.endswith(utils.ndnrtcClientInstanceName) else os.path.join(streamPrefix, utils.ndnrtcClientInstanceName)
            self.config['consume']['streams'][0]['base_prefix'] = self.basePrefix
            self.sinkPipe = os.path.join(self.runDir, 'sink')
            self.config['consume']['streams'][0]['sink']['name'] = self.sinkPipe
        self.configFile = os.path.join(self.runDir, 'consumer.cfg')
        with io.open(self.configFile, mode="w") as f:
            libconf.dump(self.config, f)
        logger.debug("saved config to %s"%self.configFile)

    def setupSigningIdentity(self):
        identity = ndnsec_getDefaultIdentity().strip()
        if not identity:
            logger.warn('failed to acquire default identity. set default identity using ndnsec. will create a new one')
            identity = '/ndnrtc-stream-phony'
            res = ndnsec_createIdentity(identity)
            if not res:
                logger.error('failed to create identity. can not start ndnrtc-client')
                raise Exception('failed to create identity. can not start ndnrtc-client')
        self.signingIdentity = identity

    def setupVerificationPolicy(self):
        self.policyFile = os.path.join(self.runDir, 'policy.conf')
        if self.options['--trust_schema']:
            logger.debug('using provided trust schema policy file %s'%self.options['--trust_schema'])
            self.policyFile = self.options['--trust_schema']
        else:
            # will compose verification file based on following rules:
            # - if there's an identity that is a prefix of provided stream prefix, 
            #       then will use this identity as trust anchor
            # - if there are no such identities, will use "any" trust anchor
            allIdentities = ndnsec_getAllIdentities()
            prefixes = [i for i in allIdentities if self.options['<stream_prefix>'].startswith(i)]
            if allIdentities and len(prefixes) > 0:
                identity = prefixes[0]
                logger.info('using identity %s as a trust anchor'%identity)
                self.saveCert(identity)
                policy = utils.samplePolicy
                policy = policy.replace('CERT_FILENAME', self.certFile)
                with io.open(self.policyFile, 'w') as f:
                    f.write(policy)
            else: # use "any"
                with io.open(self.policyFile, 'w') as f:
                    f.write(utils.samplePolicyAny)
            logger.debug('setup policy file at %s'%self.policyFile)

    def saveCert(self, identity):
        # dump cert of identity to a known file
        cert = ndnsec_dumpCert(identity)
        self.certFile = os.path.join(self.runDir, 'id.cert')
        with io.open(self.certFile, 'w') as f:
            f.write(unicode(cert))
        logger.debug('stored identity cert at %s'%self.certFile)
    
    def setupPreviewPipe(self):
        if self.options['--video_size']:
            resolution = self.options['--video_size'].split('x')
            if len(resolution) < 2:
                logger.error('incorrect video size %s'%self.options['--video_size'])
                raise Exception('incorrect video size %s'%self.options['--video_size'])
            self.videoWidth = int(resolution[0])
            self.videoHeight = int(resolution[1])
        else:
            self.videoWidth = 1280
            self.videoHeight = 720
        self.previewPipe = '%s.%dx%d'%(self.sinkPipe, self.videoWidth, self.videoHeight)
        if not os.path.exists(self.previewPipe):
            os.mkfifo(self.previewPipe)

    def createOverlayFile(self):
        self.overlayFile = os.path.join(self.runDir, 'overlay.txt')
        with io.open(self.overlayFile, 'w') as f:
            f.write(u'-')

    def startStatWatch(self):
        global statFileId, streamName
        if not self.options['--config_file']:
            self.statFile = "%s%s-%s.stat"%(statFileId, self.basePrefix.replace('/','-'), streamName)
            filePath = os.path.join(self.runDir, self.statFile)
            
            def onNewLine(statLine):
                # logger.debug('new line %s and the stats are %s'%(statLine))
                overlay = "Fetching %s"%self.basePrefix
                stats = statLine.split('\t')
                if len(stats) > 1:
                    idx = 1
                    for statKey in self.config['consume']['basic']['stat_gathering'][0]['statistics']:
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