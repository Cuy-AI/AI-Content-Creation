import os
import tempfile
from typing import Tuple, List, Dict, Optional
from datetime import timedelta
from PIL import Image, ImageOps



class ImageEditor:
    """
    Stateless image helper. All methods accept a PIL.Image and return a new PIL.Image.
    """

    def load_picture(self, path: str) -> Image.Image:
        """Load image from disk and return PIL Image."""
        return Image.open(path).convert("RGBA")

    def get_size(self, img: Image.Image) -> Tuple[int, int]:
        """Return (width, height)."""
        return img.width, img.height

    def resize_keep_aspect(self, 
            img: Image.Image, 
            target_w: Optional[int] = None,
            target_h: Optional[int] = None, 
            resample=Image.LANCZOS
        ) -> Image.Image:
        """
        Resize while keeping aspect ratio.
        At least one of target_w or target_h must be provided.
        """
        if target_w is None and target_h is None:
            raise ValueError("Provide target_w or target_h")

        w, h = img.size
        if target_w is None:
            scale = target_h / h
        elif target_h is None:
            scale = target_w / w
        else:
            scale = min(target_w / w, target_h / h)
        new_w = max(1, int(w * scale))
        new_h = max(1, int(h * scale))
        return img.resize((new_w, new_h), resample=resample)

    def resize_free(self, img: Image.Image, target_w: int, target_h: int, resample=Image.LANCZOS) -> Image.Image:
        """Resize without keeping aspect ratio."""
        return img.resize((int(target_w), int(target_h)), resample=resample)

    def rotate(self, img: Image.Image, angle: float, expand: bool = True) -> Image.Image:
        """Rotate by angle degrees. expand=True will expand output bounds."""
        return img.rotate(angle, expand=expand)

    def flip(self, img: Image.Image, axis: str = "x") -> Image.Image:
        """
        Flip image along axis:
        axis='x' -> horizontal flip (mirror)
        axis='y' -> vertical flip
        """
        if axis == "x":
            return ImageOps.mirror(img)
        elif axis == "y":
            return ImageOps.flip(img)
        else:
            raise ValueError("axis must be 'x' or 'y'")

    def cut_borders(self, img: Image.Image, left=0, top=0, right=0, bottom=0) -> Image.Image:
        """Crop borders: remove 'left' px from left, 'top' from top, etc."""
        w, h = img.size
        left = int(left)
        top = int(top)
        right = int(right)
        bottom = int(bottom)
        new_left = max(0, left)
        new_top = max(0, top)
        new_right = max(0, w - right)
        new_bottom = max(0, h - bottom)
        if new_left >= new_right or new_top >= new_bottom:
            raise ValueError("Crop parameters remove entire image")
        return img.crop((new_left, new_top, new_right, new_bottom))

    def save_image(self, img: Image.Image, path: str, format: str = "PNG") -> str:
        """
        Save image to the given path. If path is a folder, save as 'output.<ext>' in that folder.
        If the path or its parent folders do not exist, they are created.
        Returns the full path to the saved file.
        """
        if os.path.isdir(path):
            ext = format.lower()
            filename = f"output.{ext}"
            path = os.path.join(path, filename)
        else:
            parent = os.path.dirname(path)
            if parent and not os.path.exists(parent):
                os.makedirs(parent, exist_ok=True)
        img.save(path, format=format)
        return path