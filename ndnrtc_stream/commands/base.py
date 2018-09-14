"""The base command."""

import logging
from utils import *

logger = None

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
        logger = logging.getLogger(__name__)

    def run(self):
        raise NotImplementedError('You must implement the run() method yourself!')
