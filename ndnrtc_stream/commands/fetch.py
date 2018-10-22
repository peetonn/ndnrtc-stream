"""fetch command."""

import io
import libconf
import logging
import os
import tempfile

from .base import *
from json import dumps
from shutil import copyfile
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
            "framesReq", "framesPlayed", "framesInc", "skipNoKey",\
            "verifySuccess", "verifyFailure");\n\
        });\n\
    };\n\
    streams = ({\n\
        type = "video";\n\
        base_prefix = "";\n\
        name = "'+streamName+'";\n\
        thread_to_fetch = "'+threadName+'";\n\
        sink = {\n\
            name = "";\n\
            type = "pipe";\n\
            write_frame_info = false;\n\
        }\n\
    });\n\
};\n'

statCaptions = {'isent': 'Interests/sec', 'segNumRcvd': 'Segments/sec', 'appNacks': 'App Nacks', 'nacks': 'Netw Nacks', 
                'timeouts':'Timeouts', 'rtxNum':'Retransmissions', 'bytesRcvd': 'Payload Kbps', 'rawBytesRcvd':'Total Kbps', 
                'lambdaD': 'Min Pipeline', 'drdEst': 'DRD (ms)', 'jitterPlay':'Buffer size (ms)', 'framesReq': 'Frames Requested', 
                'framesPlayed': 'Frames Played', 'framesInc': 'Frames Incomplete', 'skipNoKey': 'Frames Skipped',
                'verifySuccess': 'Frames Verified', 'verifyFailure': 'Verify Failures' }
derivativeStats = ['isent', 'segNumRcvd', 'bytesRcvd', 'rawBytesRcvd']

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
        global sampleConfig, streamName
        if self.options['--config_file']:
            self.config = libconf.load(self.options['--config_file'])
        else:
            self.config = libconf.loads(sampleConfig)
            self.config['general']['log_path'] = self.runDir
            if self.options['--verbose']:
                self.config['general']['log_level'] = 'all' 
            streamPrefix = self.options['<stream_prefix>']
            if self.options['--instance_name']:
                utils.ndnrtcClientInstanceName = self.options['--instance_name']
            self.basePrefix = streamPrefix if streamPrefix.endswith(utils.ndnrtcClientInstanceName) else os.path.join(streamPrefix, utils.ndnrtcClientInstanceName)
            self.config['consume']['streams'][0]['base_prefix'] = self.basePrefix
            self.sinkPipe = os.path.join(self.runDir, 'sink')
            self.config['consume']['streams'][0]['sink']['name'] = self.sinkPipe
            if self.options['--stream_name']:
                streamName = self.options['--stream_name']
                self.config['consume']['streams'][0]['name'] = self.options['--stream_name']
            if self.options['--thread_name']:
                self.config['consume']['streams'][0]['thread_to_fetch'] = self.options['--thread_name']

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
            # - if there's a cert file file provided, use it as trust anchor
            # - if there's an identity that is a prefix of provided stream prefix, 
            #       then will use this identity as trust anchor
            # - if there are no such identities, will use "any" trust anchor
            if self.options['<cert_file>']:
                self.certFile = os.path.join(self.runDir, 'id.cert')
                copyfile(self.options['<cert_file>'], self.certFile)
                self.savePolicyFile()
            else:
                allIdentities = ndnsec_getAllIdentities()
                prefixes = [i for i in allIdentities if self.options['<stream_prefix>'].startswith(i)]
                if allIdentities and len(prefixes) > 0:
                    identity = prefixes[0]
                    logger.info('using identity %s as a trust anchor'%identity)
                    self.saveCert(identity)
                    self.savePolicyFile()
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
    
    def savePolicyFile(self):
        policy = utils.samplePolicy
        policy = policy.replace('CERT_FILENAME', self.certFile)
        with io.open(self.policyFile, 'w') as f:
            f.write(policy)

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
        global statFileId, streamName, derivativeStats
        if not self.options['--config_file']:
            self.statFile = "%s%s-%s.stat"%(statFileId, self.basePrefix.replace('/','-'), streamName)
            print("WATCHING STAT FILE "+self.statFile)
            filePath = os.path.join(self.runDir, self.statFile)
            
            derivatives = {}
            for s in derivativeStats:
                derivatives[s] = [time.time(), None]
            def onNewLine(statLine):
                now = time.time()
                overlay = "Fetching %s\n"%self.basePrefix.replace('%', '\%')
                stats = statLine.split('\t')
                if len(stats) > 1:
                    idx = 1
                    for statKey in self.config['consume']['basic']['stat_gathering'][0]['statistics']:
                        try:
                            update = True
                            caption = statCaptions[statKey]
                            value = float(stats[idx])
                            if statKey in derivativeStats: # calculate derivative for this stat
                                dT = now - derivatives[statKey][0]
                                lastValue = derivatives[statKey][1]
                                # if dT >= 1:
                                derivatives[statKey][0] = now
                                derivatives[statKey][1] = value
                                if lastValue and lastValue < value:
                                    dV = value - lastValue
                                    d = dV / dT
                                    value = d
                                    # just a hack for bytes counters to convert derivative
                                    # into Kbps
                                    if 'bytes' in statKey.lower(): 
                                        value = value * 8. / 1024.
                                else:
                                    update = False
                            if update:
                                if value - int(value) > 0:
                                    overlay += "\n%20s %-10.2f"%(caption, value)
                                else:
                                    overlay += "\n%20s %-10d"%(caption, int(value))
                            idx += 1
                        except:
                            logger.debug(sys.exc_info())
                            pass
                with open_atomic(self.overlayFile, 'w') as f:
                    f.write(overlay)

            self.statTail = Tail(filePath, onNewLine)
            self.statTail.start()

    def stopStatWatch(self):
        if self.statTail:
            self.statTail.stop()