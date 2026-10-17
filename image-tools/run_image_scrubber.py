#!/usr/bin/env python3
"""Start the Image Scrubber.

Opens a local web page where you drag & drop images. Every file is
stripped of all metadata (EXIF, GPS, camera info) on your own PC, with
an optional "tag as AI-generated" marker. Nothing is uploaded anywhere.

Usage:
    python run_image_scrubber.py            # start + open browser
    python run_image_scrubber.py --no-open  # start, print the URL only
"""
import argparse

from image_scrubber.app import serve


def main() -> None:
    parser = argparse.ArgumentParser(description="Image Scrubber — strip image metadata locally")
    parser.add_argument("--no-open", action="store_true",
                        help="Don't open a browser automatically; just print the local URL.")
    args = parser.parse_args()
    serve(open_browser=not args.no_open)


if __name__ == "__main__":
    main()
