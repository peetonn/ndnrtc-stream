""" Utils """

import logging
from subprocess import PIPE, Popen as popen

logger = logging.getLogger(__name__)

ffmpegCmd = "ffmpeg"
ffplayCmd = "ffplay"
ndnrtcClientCmd = "ndnrtc-client2"
ndnsecCmd = "ndnsec"
ndnrtcClientInstanceName = 'rtc-stream'

def startFfmpeg():
    logger.debug("startimg ffmpeg...")
    pass

def startFfplay():
    logger.debug("starting ffplay...")
    pass

def startNdnrtcClient():
    logger.debug("starting ndnrtc-client...")
    pass

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


