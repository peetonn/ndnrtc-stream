"""
ndnrtc-stream

Usage:
  ndnrtc-stream publish <stream_prefix> [-i <identity> -s <video_size> -b <bitrate> -c <config_file>]
  ndnrtc-stream fetch <stream_prefix> [-t <trust_schema> -c <config_file>]
  ndnrtc-stream -h | --help
  ndnrtc-stream --version

Options:
  -h --help                         Show this screen.
  --version                         Show version.
  -i,--identity=<ndn_identity>      NDN identity used to sign data (default identitiy is used if ommited).
  -s,--video_size=<video_size>      Video stream resolution in the form <width>x<height>.
  -b,--bitrate=<bitrate>            Video stream target encoding bitrate in Kbps.
  -c,--config_file=<config_file>    ndnrtc-client config file.
  -t,--trust_schema=<trust_schema>  Trust schema verification policy.

Examples:
  ndnrtc-stream publish /ndnrtc/first-stream
  ndnrtc-stream fetch /ndnrtc/first-stream

Help:
  For help using this tool, please open an issue on the Github repository:
  https://github.com/remap/ndnrtc-stream
"""


from inspect import getmembers, isclass

from docopt import docopt

from . import __version__ as VERSION


def main():
    """Main CLI entrypoint."""
    import ndnrtc_stream.commands
    options = docopt(__doc__, version=VERSION)

    for (k, v) in options.items(): 
        if hasattr(ndnrtc_stream.commands, k) and v:
            module = getattr(ndnrtc_stream.commands, k)
            commands = getmembers(module, isclass)
            command = [(name,cls) for (name,cls) in commands if name.lower() == k][0][1]
            ndnrtc_stream.commands = commands
            command = command(options)
            command.run()
