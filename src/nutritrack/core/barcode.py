"""Decode product barcodes (EAN-13/8, UPC-A/E) from a photo using zxing-cpp.

zxing-cpp ships native wheels for desktop platforms; if it isn't available on a device, `available()` is False and the
app falls back to typing the barcode number.
"""
from __future__ import annotations

import io


def available() -> bool:
    try:
        import zxingcpp  # noqa: F401
        from PIL import Image  # noqa: F401
        return True
    except Exception:
        return False


def decode(image_bytes: bytes) -> str | None:
    """Return the first retail barcode found in the image, or None."""
    import zxingcpp
    from PIL import Image

    img = Image.open(io.BytesIO(image_bytes))
    img.load()
    retail = {"EAN13", "EAN8", "UPCA", "UPCE"}
    results = zxingcpp.read_barcodes(img)
    for r in results:
        if r.format.name.replace("_", "").upper() in retail:
            return r.text
    return results[0].text if results else None
