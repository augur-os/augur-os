"""CLI: crop and resize an icon image. Usage: process_icon.py <src> <dst>."""
import sys


def _out(*args: object, **kwargs: object) -> None:
    sep = kwargs.get("sep", " ")
    end = kwargs.get("end", "\n")
    file = kwargs.get("file", sys.stdout)
    file.write(sep.join(str(arg) for arg in args) + str(end))


def process_icon(src: str, dst: str) -> int:
    """Crop the source image to a top-left square and resize to ≤512x512.

    Returns process exit code (0 on success, 1 on error).
    """
    try:
        from PIL import Image
    except ImportError:
        _out("PIL not found")
        return 1

    try:
        img = Image.open(src)
        w, h = img.size

        # Simple heuristic: Crop the left-most square, assuming logo is there.
        # If the image is very wide banner, h is likely the limiting factor.
        # If image is tall, we take top square.
        dim = min(w, h)

        # We want top-left square.
        cropped = img.crop((0, 0, dim, dim))

        # Resize to standard icon size for better quality downscaling.
        if dim > 512:
            cropped = cropped.resize((512, 512), Image.LANCZOS)

        cropped.save(dst)
        _out(f"Processed icon: {dim}x{dim} -> {dst}")
        return 0
    except Exception as e:
        _out(f"Error processing image: {e}")
        return 1


def main() -> int:
    if len(sys.argv) < 3:
        _out("Usage: process_icon.py <src> <dst>")
        return 1
    return process_icon(sys.argv[1], sys.argv[2])


if __name__ == "__main__":
    sys.exit(main())
