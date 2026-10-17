# tools

A growing collection of small, local tools. Every tool runs entirely on
your own PC in your browser: no accounts, no cloud, nothing uploaded anywhere.

## Networking tools (`networking-tools/`)

Troubleshoot network connection problems:

- **Remote Desktop Troubleshooter** — works out whether a firewall, the
  router/network, or the target PC itself is blocking a Windows RDP
  connection, with fix steps in order.
- **Network Stability Monitor** — graphs ping, jitter, and packet loss to
  your router and the internet over time.

```bash
cd networking-tools
python run_networking_tools.py   # all-in-one homepage menu
```

See `networking-tools/README.md` for details.

## Image tools (`image-tools/`)

Work with images locally:

- **Image Scrubber** — drag & drop images into a local web page and get
  back copies with all metadata stripped (EXIF, GPS, camera info), plus
  optional extras: remove the background (tiny on-device AI), tag as
  AI-generated, and scrub filenames to date + sequence.

```bash
python -m pip install -r image-tools/requirements.txt
cd image-tools
python run_image_scrubber.py
```

See `image-tools/README.md` for details.
