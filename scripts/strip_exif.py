"""Copy images with all metadata (EXIF, GPS, camera info) removed.

Usage: python scripts/strip_exif.py <input image or folder> <output folder>
"""
import sys
from pathlib import Path

from PIL import Image, ImageOps

EXTS = {".jpg", ".jpeg", ".png", ".tif", ".tiff", ".bmp"}


def strip(src: Path, out_dir: Path) -> Path:
    with Image.open(src) as im:
        upright = ImageOps.exif_transpose(im)  # keep phone photos the right way up
        clean = Image.new(upright.mode, upright.size)
        clean.paste(upright)  # pixels only; no metadata is copied
        dest = out_dir / src.name
        clean.save(dest)
    return dest


def main() -> None:
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    src, out_dir = Path(sys.argv[1]), Path(sys.argv[2])
    out_dir.mkdir(parents=True, exist_ok=True)
    files = [src] if src.is_file() else [p for p in src.iterdir() if p.suffix.lower() in EXTS]
    for f in files:
        print("clean:", strip(f, out_dir))


if __name__ == "__main__":
    main()
