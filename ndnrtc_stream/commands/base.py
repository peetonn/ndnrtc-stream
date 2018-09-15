"""The base command."""

from utils import *
from json import dumps
import logging, os, signal, sys, time, tempfile

logger = logging.getLogger(__name__)

class Base(object):
    """A base command."""

    def __init__(self, options, *args, **kwargs):
        global logger
        self.options = options
        self.args = args
        self.kwargs = kwargs
        if self.options["--verbose"]:
            logging.basicConfig(level = logging.DEBUG)
        else:
            logging.basicConfig(level = logging.INFO)
        ch = logging.StreamHandler(sys.stdout)
        ch.setFormatter(CustomFormatter())
        logger.propagate = False
        logger.handlers = [ch]

        logger.debug('cli options: %s'%dumps(self.options, indent=2, sort_keys=True))
        # temp run directory
        self.runDir = tempfile.mkdtemp(prefix='ndnrtc-stream.')
        logger.debug("temporary runtime directory %s"%self.runDir)

        signal.signal(signal.SIGINT, self.signal_handler)

    def run(self):
        raise NotImplementedError('You must implement the run() method yourself!')

    def signal_handler(self, sig, frame):
        logger.warn('caught stop signal...')
        self.stopChildren()

    def stopChildren(self):
        logger.debug("stopping child processes...")
        try:
            for p in self.childrenProcs:
                self.kill(p)
        except:
            pass
        logger.debug("child processes stopped")

    def kill(self, proc):
        # os.kill(proc.pid, signal.SIGTERM)
        if proc.poll() == None:
            proc.terminate()