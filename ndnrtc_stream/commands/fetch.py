"""fetch command."""

from .base import Base
from json import dumps

class Fetch(Base):
    def __init__(self, options, *args, **kwargs):
        Base.__init__(self, options, args, kwargs)

    def run(self):
        print("hey running fetching!")
        print('You supplied the following options:', dumps(self.options, indent=2, sort_keys=True))
