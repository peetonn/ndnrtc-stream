""" Utils """

import logging
from subprocess import PIPE, Popen as popen

logger = logging.getLogger(__name__)

ffmpegCmd = "ffmpeg"
ffplayCmd = "ffplay"
ndnrtcClientCmd = "ndnrtc-client2"
ndnsecCmd = "ndnsec"
ndnrtcClientInstanceName = 'rtc-stream'
defaultRunTime = 10000

samplePolicyAny = \
u'validator\n\
{\n\
    rule\n\
    {\n\
        id "Validation Rule"\n\
        for data\n\
        checker\n\
        {\n\
            type hierarchical\n\
            sig-type rsa-sha256\n\
        }\n\
    }\n\
    trust-anchor\n\
    {\n\
        type any\n\
    }\n\
}'

samplePolicy = \
u'validator\n\
{\n\
    rule\n\
    {\n\
        id "Validation Rule"\n\
        for data\n\
        checker\n\
        {\n\
            type hierarchical\n\
            sig-type rsa-sha256\n\
        }\n\
    }\n\
    trust-anchor\n\
    {\n\
        type file\n\
        file-name "CERT_FILENAME"\n\
    }\n\
}'


def startFfplay(previewPipe, w, h):
    proc = popen([ffplayCmd, '-f', 'rawvideo', 
                    '-pixel_format', '0rgb',
                    '-video_size', '%dx%d'%(w,h),
                    '-i', previewPipe],
                  stdout=PIPE, 
                  stderr=PIPE)
    logger.debug('started ffplay to read frames of %dx%d size from %s'%(w,h, previewPipe))
    return proc

def startFfmpeg(cameraPipe, previewPipe, w,h):
    proc = popen([ffmpegCmd,'-y',
                     '-f', 'avfoundation',
                    '-pixel_format', '0rgb',
                    '-framerate', '25',
                    '-video_size', '%dx%d'%(w,h),
                    '-i', '0', 
                    '-map', '0:v',
                    '-c', 'copy',
                    '-f', 'rawvideo',
                    cameraPipe,
                    '-map', '0:v',
                    '-c', 'copy',
                    '-f', 'rawvideo',
                    previewPipe],
                    stdout=PIPE,
                    stderr=PIPE)
    logger.debug('started ffmpeg to read frames of %dx%d from camera into camera pipe %s and preview pipe %s'%(w,h,cameraPipe, previewPipe))
    return proc

def startNdnrtcClient(configFile, signingIdentity, verificationPolicy):
    global defaultRunTime
    proc = popen([ndnrtcClientCmd, '-c', configFile,
                    '-s', signingIdentity,
                    '-p', verificationPolicy,
                    '-t', str(defaultRunTime),
                    '-i', ndnrtcClientInstanceName],
                    stdout=PIPE,
                    stderr=PIPE)
    logger.debug('started ndnrtc-client process.')
    return proc

def ndnsec_checkIdentity(identityName):
    ndnsecList = popen([ndnsecCmd, 'list'], stdout=PIPE)
    ndnsecList.wait()
    if ndnsecList.returncode == 0:
        output = ndnsecList.communicate()[0]
        return (identityName in output)
    return False

def ndnsec_createIdentity(identityName):
    if not ndnsec_checkIdentity(identityName):
        logger.info('creating self-signed identity %s'%identityName)

        ndnsecInstallCert = popen([ndnsecCmd, 'cert-install', '-'], stdin=PIPE, stdout=PIPE)
        ndnsecInstallCertStdIn = ndnsecInstallCert.stdin
        ndnsecKeyGen = popen([ndnsecCmd, 'key-gen', '-i', identityName], stdout=ndnsecInstallCertStdIn)
        output = ndnsecInstallCert.communicate()[0]
        if ndnsecInstallCert.returncode == 0:
            return ndnsec_checkIdentity(identityName)

def ndnsec_getDefaultIdentity():
    ndnsecProc = popen([ndnsecCmd, 'get-default'], stdout=PIPE)
    output = ndnsecProc.communicate()[0]
    if ndnsecProc.returncode == 0:
        return output
    return None

def ndnsec_getAllIdentities():
    ndnsecProc = popen([ndnsecCmd, 'list'], stdout=PIPE)
    output = ndnsecProc.communicate()[0]
    if ndnsecProc.returncode == 0:
        ids = []
        lines = [l.strip() for l in output.split('\n') if l != '']
        for identity in lines:
            if  '*' in identity and len(identity.split(' ')) == 2: # found default identity
                identity = identity.split(' ')[1]
            ids.append(identity)
        return ids
    return None

def ndnsec_dumpCert(identity):
    ndnsecProc = popen([ndnsecCmd, 'cert-dump', '-i', identity], stdout=PIPE)
    output = ndnsecProc.communicate()[0]
    if ndnsecProc.returncode == 0:
        return output
    return None

