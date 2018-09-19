""" Utils """

import io, logging, os, sys, threading, time
from subprocess import PIPE, Popen as popen
from threading import Thread
import tempfile as tmp
from contextlib import contextmanager

ffmpegCmd = "ffmpeg"
ffplayCmd = "ffplay"
ndnrtcClientCmd = "ndnrtc-client"
ndnsecCmd = "ndnsec"
ndnrtcClientInstanceName = 'rtc-stream'
defaultRunTime = 10000
streamName = "camera"
statFileId = "overlay-stats"

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

# adapted from https://stackoverflow.com/a/6290946/846340
class CustomFormatter(logging.Formatter):
    normal_fmt  = '%(asctime)s [%(levelname)s] : %(message)s'
    dbg_fmt  = '%(asctime)s [%(levelname)s] - %(name)s : %(message)s'

    def __init__(self, fmt='%(asctime)s [%(levelname)s] : %(message)s'):
        logging.Formatter.__init__(self, fmt)

    def format(self, record):
        # Save the original format configured by the user
        # when the logger formatter was instantiated
        format_orig = self._fmt
        # Replace the original format with one customized by logging level
        if logging.getLogger(record.name).getEffectiveLevel() == logging.DEBUG:
            self._fmt = CustomFormatter.dbg_fmt
        else:
            self._fmt = CustomFormatter.normal_fmt
        # Call the original formatter class to do the grunt work
        result = logging.Formatter.format(self, record)
        
        # Restore the original format configured by the user
        self._fmt = format_orig
        return result

logger = logging.getLogger(__name__)
ch = logging.StreamHandler(sys.stdout)
ch.setFormatter(CustomFormatter())
logger.propagate = False
logger.handlers = [ch]

def checkNfdIsRunning():
    proc = popen(['nfd-status'], stdout=PIPE)
    out = proc.communicate()[0]
    if proc.returncode != 0:
        logger.error('apparently, NFD is not running. please start NFD to use this app')
        sys.exit(1)

def startFfplay(previewPipe, w, h, overlayFile=''):
    proc = popen([ffplayCmd, '-f', 'rawvideo', 
                    # '-vf', 'drawtext=text=\'%{localtime} '+str+'\': x=10: y=10: fontcolor=white: fontsize=20: box=1: boxcolor=0x00000000@1',
                    '-vf', 'drawtext=textfile='+overlayFile+':reload=1: x=10: y=10: fontcolor=white: fontfile=/System/Library/Fonts/Courier.dfont: fontsize=20: box=1: boxcolor=0x00000000@0.3',
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
    proc = popen([ndnrtcClientCmd, '-v', '-c', configFile,
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

class Tail(object):
    running = False

    def __init__(self, fileName, onNewLine):
        self.fileName = fileName
        self.onNewLine = onNewLine
        self.thread = Thread(target = self.run)

    def start(self):
        self.running = True
        self.thread.start()

    def stop(self):
        self.running = False
        self.thread.join()

    def run(self):
        try:
            with io.open(self.fileName, 'r') as f:
                f.seek(0, 2) # seek to the end of file
                while self.running:
                    line = f.readline()
                    if line == '': # empty line
                        time.sleep(0.05)
                    else:
                        if self.onNewLine:
                            self.onNewLine(line)
        except (OSError, IOError) as e:
            time.sleep(0.2)
            if self.running:
                self.run()

@contextmanager
def tempfile(suffix='', dir=None):
    """ Context for temporary file.

    Will find a free temporary filename upon entering
    and will try to delete the file on leaving, even in case of an exception.

    Parameters
    ----------
    suffix : string
        optional file suffix
    dir : string
        optional directory to save temporary file in
    """

    tf = tmp.NamedTemporaryFile(delete=False, suffix=suffix, dir=dir)
    tf.file.close()
    try:
        yield tf.name
    finally:
        try:
            os.remove(tf.name)
        except OSError as e:
            if e.errno == 2:
                pass
            else:
                raise

@contextmanager
def open_atomic(filepath, *args, **kwargs):
    """ Open temporary file object that atomically moves to destination upon
    exiting.

    Allows reading and writing to and from the same filename.

    The file will not be moved to destination in case of an exception.

    Parameters
    ----------
    filepath : string
        the file path to be opened
    fsync : bool
        whether to force write the file to disk
    *args : mixed
        Any valid arguments for :code:`open`
    **kwargs : mixed
        Any valid keyword arguments for :code:`open`
    """
    fsync = kwargs.get('fsync', False)

    with tempfile(dir=os.path.dirname(os.path.abspath(filepath))) as tmppath:
        with open(tmppath, *args, **kwargs) as file:
            try:
                yield file
            finally:
                if fsync:
                    file.flush()
                    os.fsync(file.fileno())
        os.rename(tmppath, filepath)

def dumpOutput(out, filename):
    def dump(out, filename):
        with io.open(filename, 'w') as f:
            while True:
                line = out.readline()
                f.write(unicode(line))
                f.flush()
            logger.debug('closing %s'%filename)
            out.close()
    t = Thread(target = dump, args = (out, filename))
    t.daemon = True
    t.start()

