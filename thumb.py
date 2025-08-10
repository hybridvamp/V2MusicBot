
import asyncio
from io import BytesIO

import httpx
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont, ImageOps
from aiofiles.os import path as aiopath

# from TgMusic.logger import LOGGER

from pathlib import Path
from typing import Union
from pydantic import BaseModel

import logging
from logging.handlers import RotatingFileHandler, TimedRotatingFileHandler
# Configure logging
logging.basicConfig(level=logging.DEBUG)

LOGGER = logging.getLogger("TgMusicBot")

class CachedTrack(BaseModel):
    url: str
    name: str
    artist: str
    loop: int
    user: str
    file_path: Union[str, Path]
    thumbnail: str
    track_id: str
    duration: int = 0
    is_video: bool
    platform: str

FONTS = {
    "cfont": ImageFont.truetype("TgMusic/modules/utils/cfont.ttf", 15),
    "dfont": ImageFont.truetype("TgMusic/modules/utils/font2.otf", 15),
    "nfont": ImageFont.truetype("TgMusic/modules/utils/font.ttf", 10),
    "tfont": ImageFont.truetype("TgMusic/modules/utils/font.ttf", 20),
}


def resize_youtube_thumbnail(img: Image.Image) -> Image.Image:
    """
    Resize a YouTube thumbnail to 640x640 while keeping important content.

    It crops the center of the image after resizing.
    """
    target_size = 640
    aspect_ratio = img.width / img.height

    if aspect_ratio > 1:
        new_width = int(target_size * aspect_ratio)
        new_height = target_size
    else:
        new_width = target_size
        new_height = int(target_size / aspect_ratio)

    img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)

    # Crop to 640x640 (center crop)
    left = (img.width - target_size) // 2
    top = (img.height - target_size) // 2
    right = left + target_size
    bottom = top + target_size

    return img.crop((left, top, right, bottom))


def resize_jiosaavn_thumbnail(img: Image.Image) -> Image.Image:
    """
    Resize a JioSaavn thumbnail from 500x500 to 600x600.

    It upscales the image while preserving quality.
    """
    target_size = 600
    img = img.resize((target_size, target_size), Image.Resampling.LANCZOS)
    return img


async def fetch_image(url: str) -> Image.Image | None:
    """
    Fetches an image from the given URL, resizes it if necessary for JioSaavn and
    YouTube thumbnails, and returns the loaded image as a PIL Image object, or None on
    failure.

    Args:
        url (str): URL of the image to fetch.

    Returns:
        Image.Image | None: The fetched and possibly resized image, or None if the fetch fails.
    """
    if not url:
        return None

    async with httpx.AsyncClient() as client:
        try:
            if url.startswith("https://is1-ssl.mzstatic.com"):
                url = url.replace("500x500bb.jpg", "600x600bb.jpg")
            response = await client.get(url, timeout=5)
            response.raise_for_status()
            img = Image.open(BytesIO(response.content)).convert("RGBA")
            if url.startswith("https://i.ytimg.com"):
                img = resize_youtube_thumbnail(img)
            elif url.startswith("http://c.saavncdn.com") or url.startswith(
                "https://i1.sndcdn"
            ):
                img = resize_jiosaavn_thumbnail(img)
            return img
        except Exception as e:
            LOGGER.error("Image loading error: %s", e)
            return None


def clean_text(text: str, limit: int = 17) -> str:
    """
    Sanitizes and truncates text to fit within the limit.
    """
    text = text.strip()
    return f"{text[:limit - 3]}..." if len(text) > limit else text


def add_controls(img: Image.Image) -> Image.Image:
    """
    Adds blurred background effect and overlay controls.
    """
    img = img.filter(ImageFilter.GaussianBlur(25))
    box = (120, 120, 520, 480)

    region = img.crop(box)
    controls = Image.open("TgMusic/modules/utils/controls.png").convert("RGBA")
    dark_region = ImageEnhance.Brightness(region).enhance(0.5)

    mask = Image.new("L", dark_region.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle(
        (0, 0, box[2] - box[0], box[3] - box[1]), 40, fill=255
    )

    img.paste(dark_region, box, mask)
    img.paste(controls, (135, 305), controls)

    return img


def make_sq(image: Image.Image, size: int = 125) -> Image.Image:
    """
    Crops an image into a rounded square.
    """
    width, height = image.size
    side_length = min(width, height)
    crop = image.crop(
        (
            (width - side_length) // 2,
            (height - side_length) // 2,
            (width + side_length) // 2,
            (height + side_length) // 2,
        )
    )
    resize = crop.resize((size, size), Image.Resampling.LANCZOS)

    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, size, size), radius=30, fill=255)

    rounded = ImageOps.fit(resize, (size, size))
    rounded.putalpha(mask)
    return rounded


def get_duration(duration: int, time: str = "0:24") -> str:
    """
    Calculates remaining duration.
    """
    try:
        m1, s1 = divmod(duration, 60)
        m2, s2 = map(int, time.split(":"))
        sec = (m1 * 60 + s1) - (m2 * 60 + s2)
        _min, sec = divmod(sec, 60)
        return f"{_min}:{sec:02d}"
    except Exception as e:
        LOGGER.error("Duration calculation error: %s", e)
        return "0:00"


async def gen_thumb(song: CachedTrack) -> str:
    """
    Generates and saves a thumbnail for the song using the provided UI template.
    Now allows adjusting title/artist vertical position and font sizes.
    """

    # === CONFIGURABLE SETTINGS ===
    TITLE_FONT_SIZE = 50     # base title font size
    ARTIST_FONT_SIZE = 22    # base artist font size
    TITLE_UP_OFFSET = -75   # negative = move up, positive = move down
    ARTIST_UP_OFFSET = -5    # negative = move up, positive = move down
    # ==============================

    save_dir = f"database/photos/{song.track_id}.png"
    if await aiopath.exists(save_dir):
        return save_dir

    title_raw = (song.name or "").strip() or "Unknown Title"
    artist_raw = (song.artist or "Unknown Artist").strip()
    duration = int(song.duration or 0)

    # Load template
    template_paths = [
        "TgMusic/modules/utils/thumb.png",
        "thumb.png",
        "/mnt/data/Uh6Il.png",
    ]
    base_img = None
    for p in template_paths:
        try:
            base_img = Image.open(p).convert("RGBA")
            break
        except Exception:
            continue
    if base_img is None:
        LOGGER.error("Template image loading error.")
        return ""

    W, H = base_img.size

    left_min_x = int(82 / 1280 * W)
    left_min_y = int(76 / 720 * H)
    left_max_x = int(649 / 1280 * W)
    left_max_y = int(643 / 720 * H)
    left_w = left_max_x - left_min_x
    left_h = left_max_y - left_min_y

    wave_min_x = int(692 / 1280 * W)
    wave_min_y = int(229 / 720 * H)
    wave_max_x = int(1192 / 1280 * W)
    wave_max_y = int(626 / 720 * H)

    prog_min_x = int(696 / 1280 * W)
    prog_min_y = int(414 / 720 * H)
    prog_max_x = int(1201 / 1280 * W)
    prog_max_y = int(453 / 720 * H)

    album_padding = max(16, int(28 / 1280 * W))
    album_size = min(left_w, left_h) - album_padding * 2
    album_size = max(32, album_size)
    cover_x = left_min_x + (left_w - album_size) // 2
    cover_y = left_min_y + (left_h - album_size) // 2

    thumb_img = await fetch_image(song.thumbnail)
    if not thumb_img:
        LOGGER.error("No thumbnail for song %s", song.track_id)
        return ""

    try:
        album_cover = make_sq(thumb_img, album_size)
    except Exception:
        w0, h0 = thumb_img.size
        s = min(w0, h0)
        crop = thumb_img.crop(((w0 - s) // 2, (h0 - s) // 2, (w0 + s) // 2, (h0 + s) // 2))
        album_cover = crop.resize((album_size, album_size), Image.Resampling.LANCZOS).convert("RGBA")

    try:
        radius = max(12, int(28 / 1280 * W))
        mask = Image.new("L", (album_size, album_size), 0)
        ImageDraw.Draw(mask).rounded_rectangle((0, 0, album_size, album_size), radius=radius, fill=255)
        album_cover.putalpha(mask)
    except Exception:
        pass

    base_img.paste(album_cover, (cover_x, cover_y), album_cover)

    draw = ImageDraw.Draw(base_img)

    def _get_font(path, size):
        try:
            return ImageFont.truetype(path, size)
        except Exception:
            return ImageFont.load_default()

    title_font = _get_font("TgMusic/modules/utils/font.ttf", int(TITLE_FONT_SIZE / 1280 * W))
    artist_font = _get_font("TgMusic/modules/utils/font.ttf", int(ARTIST_FONT_SIZE / 1280 * W))
    dur_font = _get_font("TgMusic/modules/utils/font.ttf", int(25 / 1280 * W))

    title_color = (0, 0, 0)
    artist_color = (50, 50, 50)
    dur_color = (20, 20, 20)

    title_x = wave_min_x + int(18 / 1280 * W)
    title_top_margin = int(70 / 720 * H)
    title_y = max(int(16 / 720 * H), wave_min_y - title_top_margin) + TITLE_UP_OFFSET

    max_title_width = wave_max_x - title_x - int(18 / 1280 * W)
    if max_title_width <= 0:
        max_title_width = int(420 / 1280 * W)

    def wrap_text(text, font, max_w, max_lines=2):
        words = text.split()
        if not words:
            return []
        lines = []
        cur = words[0]
        for w in words[1:]:
            test = cur + " " + w
            bbox = draw.textbbox((0, 0), test, font=font)
            if bbox[2] - bbox[0] <= max_w:
                cur = test
            else:
                lines.append(cur)
                cur = w
        lines.append(cur)
        if len(lines) > max_lines:
            lines = lines[:max_lines]
        return lines

    title_lines = wrap_text(title_raw, title_font, max_title_width, max_lines=2)
    y_cursor = title_y
    line_spacing = int(title_font.size * 1.05)
    for line in title_lines:
        draw.text((title_x, y_cursor), line, font=title_font, fill=title_color)
        y_cursor += line_spacing

    artist_max_w = max_title_width
    artist_line = artist_raw
    if draw.textlength(artist_line, font=artist_font) > artist_max_w:
        while draw.textlength(artist_line + "...", font=artist_font) > artist_max_w and len(artist_line) > 0:
            artist_line = artist_line[:-1]
        artist_line = artist_line.rstrip() + "..."

    artist_y = y_cursor + int(6 / 720 * H) + ARTIST_UP_OFFSET
    draw.text((title_x, artist_y), artist_line, font=artist_font, fill=artist_color)

    def format_duration(sec):
        m, s = divmod(int(sec), 60)
        return f"{m}:{s:02d}"

    dur_text = format_duration(duration)
    dur_x = prog_max_x + int(6 / 1280 * W)
    dur_y = prog_min_y + ((prog_max_y - prog_min_y) - dur_font.size) // 2
    for ox, oy in [(0, 0), (1, 0)]:
        draw.text((dur_x + ox, dur_y + oy), dur_text, font=dur_font, fill=dur_color)

    Path(save_dir).parent.mkdir(parents=True, exist_ok=True)
    await asyncio.to_thread(base_img.save, save_dir)
    return save_dir if await aiopath.exists(save_dir) else ""


def generate_random_string(length: int = 5) -> str:
    """
    Generates a random alphanumeric string of the specified length.
    """
    import random
    import string
    return ''.join(random.choices(string.ascii_letters + string.digits, k=length))

SONG = CachedTrack(
    url="https://www.youtube.com/watch?v=0WM6-noV9ZY",
    name="Alan Walker On My Way - Sabrina Carpender, Farruko & Conor Maynard",
    artist="Alan Walker, Sabrina Carpenter, Farruko, Conor Maynard",
    loop=0,
    user="example_user",
    file_path="example_song.mp3",
    thumbnail="https://img.youtube.com/vi/0WM6-noV9ZY/maxresdefault.jpg",
    track_id=generate_random_string(),
    duration=240,
    is_video=False,
    platform="YouTube"
)

import asyncio
# generate thumbnail for the example song
async def main():
    thumb_path = await gen_thumb(SONG)
    print(f"Thumbnail saved at: {thumb_path}")
    return thumb_path

#run the main function
if __name__ == "__main__":
    asyncio.run(main())
