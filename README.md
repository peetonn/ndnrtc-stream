# ndnrtc-stream
This is a Python application, wrapper for ndnrtc-client (need to be installed) and supporting tools (like `ffmpeg` and `ffplay`) for quick&amp;easy video streaming over NDN.

## Prerequisistes

* [NFD](https://github.com/named-data/NFD)
* `virtualenv`
* [`ndnrtc-client`](https://github.com/remap/homebrew-ndnrtc)

```
pip install virtualenv
brew update
brew tap remap/ndnrtc
brew install ndnrtc
```

## Install

### From source

Inside cloned repo:

```
virtualenv env && source env/bin/activate
pip install .
```

### Using homebrew

```
brew tap remap/ndnrtc
brew install ndnrtc ndnrtc-stream
```

## Use

1. Configure [NFD security]()
2. Generate new self-signed identity (or use existing one) which will be used for signing data:

```
ndnsec-keygen /ndnrtc | ndnsec-install-cert -
ndnsec list
```

3. Publish RTC stream:

```
ndnrtc-stream publish /ndnrtc
```

4. In a separate terminal window, fetch stream:

```
ndnrtc-stream fetch /ndnrtc/rtc-stream
```

## Fetching from remote machine

If you want to fetch video published bby `ndnrtc-stream` from remote machine, make sure you have registered NFD route for this machine. Usually, UDP tunnels are used (NDN over UDP) to establish routes between machines:

```
nfdc face create udp://<remote-machine-ip-address>
nfdc route add ndn://ndnrtc <face-id>
ndnrtc-stream fetch /ndnrtc/rtc-stream
```
