# Image Tools

Small, local tools for working with images. Everything runs entirely on
your own PC in your browser: no accounts, no cloud, nothing uploaded anywhere.

## Image Scrubber (`run_image_scrubber.py`)

Drag & drop images into a local web page and get back copies with **all
metadata stripped**: EXIF, GPS location, camera make/model, timestamps —
everything. Useful before sharing or posting photos.

- Optional **"Tag as AI-generated"** checkbox adds a small AI-generated
  marker to the cleaned file (EXIF UserComment on JPEG/WebP, PNG text
  chunk on PNG) so the file is honestly labeled without leaking anything
  else.
- Supports JPG, PNG, WebP, TIFF, BMP. EXIF orientation is applied first,
  so cleaned photos display exactly as the originals did.
- Cleaned files download individually, or all at once as a zip.

```bash
python -m pip install Pillow
python run_image_scrubber.py            # start + open browser
python run_image_scrubber.py --no-open  # start, print the URL only
```

Run the checks with `python -m pytest` (or `python tests/test_scrub.py`
with no pytest installed).
