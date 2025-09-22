import os
import subprocess
import tempfile
import shutil
import json
from typing import Tuple, Optional, List, Union
from datetime import timedelta

# Optional GPU detection for encoder selection
try:
    import torch
    _HAS_TORCH = True
except Exception:
    _HAS_TORCH = False


class VideoEditor:
    """
    Functional, path-based VideoEditor using ffmpeg/ffprobe.
    Methods accept input_path (and optional output_path) and return output_path.
    """

    def __init__(self, temp_dir: Optional[str] = None):
        """
        :param temp_dir: optional folder for temporary files. If None, a temp folder is created.
        """
        self._ensure_ffmpeg()
        if temp_dir:
            os.makedirs(temp_dir, exist_ok=True)
            self.temp_dir = temp_dir
            self._own_temp = False
        else:
            self.temp_dir = tempfile.mkdtemp(prefix="veditor_")
            self._own_temp = True
        self._temp_files = set()

    # -------------------
    # Helpers
    # -------------------
    def _ensure_ffmpeg(self):
        if shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None:
            raise RuntimeError("ffmpeg and ffprobe must be installed and available on PATH.")

    def _probe(self, path: str) -> dict:
        cmd = ["ffprobe", "-v", "error", "-print_format", "json", "-show_format", "-show_streams", path]
        out = self._run(cmd)
        return json.loads(out)

    def _run(self, cmd: List[str]):
        # print("Running:", ' '.join(cmd))
        proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
        if proc.returncode != 0:
            raise RuntimeError(f"ffmpeg/ffprobe command failed:\n{' '.join(cmd)}\nSTDOUT:\n{proc.stdout}\nSTDERR:\n{proc.stderr}")
        return proc.stdout

    def _choose_encoder(self) -> Tuple[str, List[str]]:
        """
        Return (codec_name, params_list) adapted to GPU if available.
        Uses NVENC (h264_nvenc) when torch.cuda.is_available() is True.
        """
        if _HAS_TORCH and torch.cuda.is_available():
            # NVENC params: tweak as desired
            # return "h264_nvenc", ["-preset", "fast", "-rc", "vbr_hq", "-cq", "19"]
            return "libx264", ["-preset", "fast", "-crf", "23", "-threads", str(max(1, os.cpu_count() or 1))]
        else:
            # CPU x264
            return "libx264", ["-preset", "fast", "-crf", "23", "-threads", str(max(1, os.cpu_count() or 1))]


    # -------------------
    # Handle temp files
    # -------------------
    def _mktemp(self, suffix: str = ".mp4") -> str:
        fd, path = tempfile.mkstemp(suffix=suffix, dir=self.temp_dir)
        os.close(fd)
        self._temp_files.add(path)
        return path

    def remove_temp(self, paths: Union[str, List[str]]):
        """
        Remove one temp path or list of paths. If path is in tracked temp files, remove from set.
        """
        if isinstance(paths, str):
            paths = [paths]
        for p in paths:
            try:
                if os.path.exists(p): os.remove(p)
                if p in self._temp_files: self._temp_files.remove(p)
            except Exception:
                pass

    def list_temp(self) -> List[str]:
        """Return list of tracked temp files."""
        return list(self._temp_files)

    def cleanup(self):
        """Remove all tracked temp files and optionally temp dir created by this instance."""
        for p in list(self._temp_files):
            try:
                if os.path.exists(p): os.remove(p)
            except Exception:
                pass
            self._temp_files.discard(p)
        if self._own_temp and os.path.isdir(self.temp_dir):
            try: shutil.rmtree(self.temp_dir)
            except Exception: pass


    # -------------------
    # Get video metadata
    # -------------------
    def get_size(self, input_path: str) -> Tuple[int, int]:
        """Return (width, height) for the given video path."""
        meta = self._probe(input_path)
        for s in meta.get("streams", []):
            if s.get("codec_type") == "video":
                return int(s["width"]), int(s["height"])
        raise RuntimeError("No video stream found")

    def get_duration(self, input_path: str) -> float:
        """Return duration in seconds for the given video path."""
        meta = self._probe(input_path)
        fmt = meta.get("format", {})
        if fmt.get("duration"):
            return float(fmt["duration"])
        # fallback to stream duration
        for s in meta.get("streams", []):
            if s.get("codec_type") == "video" and s.get("duration"):
                return float(s["duration"])
        return 0.0

    def get_ratio(self, input_path: str) -> str:
        """Return aspect ratio as string "W:H" (e.g. "16:9")"""
        w, h = self.get_size(input_path)
        def gcd(a: int, b: int) -> int:
            while b:
                a, b = b, a % b
            return a
        g = gcd(w, h)
        return f"{w//g}:{h//g}"

    # -------------------
    # Core operations
    # -------------------
    def cut(
        self, 
        input_path, 
        start, 
        end=None, 
        output_path=None, 
        reencode=False
    ) -> str:
        """
        Cuts a portion of a video from start to end.

        Parameters:
        -----------
        input_path : str
            Path to input video file.
        start : float or str
            Start time (seconds or "hh:mm:ss").
        end : float or str
            End time (seconds or "hh:mm:ss").
        output_path : str, optional
            Output file path. If None, a temp file is created.
        reencode : bool
            If True, re-encode with libx264 for frame accuracy.
            If False, use stream copy (much faster, but cuts at keyframes).
        """

        if output_path is None: output_path = self._mktemp(".mp4")
        else: os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)

        codec = ["-c", "copy"] if not reencode else ["-c:v", "libx264", "-c:a", "aac"]

        cmd = ["ffmpeg", "-y", "-i", input_path, "-ss", str(start)]
        if end is not None: cmd += ["-to", str(end)]
        cmd += [*codec, output_path]

        self._run(cmd)
        return output_path


    def replace_audio(
        self,
        input_path: str,
        audio_path: str,
        output_path: Optional[str] = None,
        start_time: float = 0.0
    ) -> str:
        """
        Replace (or add) the audio track of a video using adelay for offset,
        but do NOT re-encode the video stream (we copy the video).

        - start_time: seconds into the video where the new audio should begin.
        - If audio would overflow the video, it's trimmed so it fits.
        - If start_time >= video_duration, outputs the video with NO audio.
        """
        if output_path is None: output_path = self._mktemp(".mp4")
        else: os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)

        video_duration = self.get_duration(input_path)
        audio_duration = self.get_duration(audio_path)

        # If start time is at/after video end, just produce the video without audio.
        if start_time >= video_duration:
            cmd = [
                "ffmpeg", "-y",
                "-i", input_path,
                "-map", "0:v",
                "-c:v", "copy",
                "-an",  # no audio
                output_path
            ]
            self._run(cmd)
            self._temp_files.add(output_path)
            return output_path

        # Audio must fit within the video; compute effective maximum audio portion.
        # We'll use atrim=0:video_duration after adelay to ensure audio doesn't exceed video length.
        delay_ms = int(round(start_time * 1000))
        need_filter = (delay_ms > 0) or (audio_duration > (video_duration - start_time))

        if not need_filter:
            # Simple fast path: no delay, no trim required — just map video and audio, copy video.
            cmd = [
                "ffmpeg", "-y",
                "-i", input_path,
                "-i", audio_path,
                "-map", "0:v:0",
                "-map", "1:a:0",
                "-c:v", "copy",
                "-c:a", "aac", "-b:a", "192k",
                output_path
            ]
        else:
            # Use adelay to shift the audio, then trim to the video's duration (so it never overflows).
            # adelay={ms}:all=1 delays all channels. atrim=0:video_duration ensures audio <= video_duration.
            filter_complex = (
                f"[1:a]adelay={delay_ms}:all=1,atrim=0:{video_duration:.3f},asetpts=PTS-STARTPTS[aud]"
            )
            cmd = [
                "ffmpeg", "-y",
                "-i", input_path,
                "-i", audio_path,
                "-filter_complex", filter_complex,
                "-map", "0:v:0",     # always keep the video stream (copied)
                "-map", "[aud]",     # processed audio
                "-c:v", "copy",
                "-c:a", "aac", "-b:a", "192k",
                output_path
            ]

        self._run(cmd)
        return output_path


    def join(
        self,
        inputs: List[str],
        output_path: Optional[str] = None,
        reencode: bool = False
    ) -> str:
        """
        Concatenate multiple videos sequentially.

        Parameters:
        -----------
        inputs : List[str]
            List of video paths to concatenate in order.
        output_path : str, optional
            Path for the output concatenated video. If None, a temp file is created.
        reencode : bool
            If False (default), tries to use stream copy (fast, no re-encode).
            If True, always re-encodes to a safe format (libx264 + aac).

        Returns:
        --------
        str
            Path to the concatenated video.
        """
        if len(inputs) < 2:
            raise ValueError("Need at least two videos to join.")

        if output_path is None: output_path = self._mktemp(".mp4")
        else: os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)

        if not reencode:
            # Fast concat via concat demuxer
            concat_list = os.path.join(self.temp_dir, "concat.txt")
            with open(concat_list, "w", encoding="utf-8") as f:
                for path in inputs:
                    f.write(f"file '{os.path.abspath(path)}'\n")

            cmd = [
                "ffmpeg", "-y",
                "-f", "concat", "-safe", "0",
                "-i", concat_list,
                "-c", "copy",
                output_path
            ]

            try:
                self._run(cmd)
                self._temp_files.add(output_path)
                os.remove(concat_list)
                return output_path
            except RuntimeError as e:
                # If concat fails (codec mismatch), fall back to re-encode
                print("Stream copy concat failed, falling back to re-encode:", e)
                reencode = True

        if reencode:
            # Build input list
            ff_inputs = []
            filter_parts = []
            for i, _ in enumerate(inputs):
                ff_inputs += ["-i", inputs[i]]
                filter_parts.append(f"[{i}:v:0][{i}:a:0]")

            # Filter: concat all N videos
            filter_complex = "".join(filter_parts) + f"concat=n={len(inputs)}:v=1:a=1[outv][outa]"

            codec, params = self._choose_encoder()
            cmd = [
                "ffmpeg", "-y",
                *ff_inputs,
                "-filter_complex", filter_complex,
                "-map", "[outv]", "-map", "[outa]",
                "-c:v", codec, *params,
                "-c:a", "aac", "-b:a", "192k",
                "-movflags", "+faststart",
                output_path
            ]
            self._run(cmd)
            return output_path


    def insert_images(
        self,
        input_path: str,
        images: List[dict],
        output_path: Optional[str] = None
    ) -> str:
        """
        Overlay multiple images on the video in a single re-encode pass.
        Adding all the images on a single call (single re-encoding) is the fastest way
        
        Parameters:
        -----------
        input_path : str
            Path to the base video.
        images : List[dict]
            Each dict must contain:
            - "image": path to image file or PIL.Image object
            - "start": start time in seconds
            - "end": end time in seconds
            - "x": x position
            - "y": y position
        output_path : str, optional
            Where to save the final video. If None, a temp file is used.

        Returns:
        --------
        str
            Path to output video.
        """
        if output_path is None: output_path = self._mktemp(".mp4")
        else: os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)

        # Prepare inputs
        ff_inputs = ["-i", input_path]
        filter_parts = []
        input_index = 1  # 0 is the main video
        prev_label = "0:v"

        temp_images = []

        for idx, img in enumerate(images):
            image = img["image"]
            start = img["start"]
            end = img["end"]
            x = img.get("x", 0)
            y = img.get("y", 0)

            # Handle PIL.Image by saving to temp PNG
            if hasattr(image, "save"):  # PIL image
                tmp_img = self._mktemp(".png")
                image.save(tmp_img)
                image_path = tmp_img
                temp_images.append(tmp_img)
            else:
                image_path = image

            ff_inputs += ["-i", image_path]

            out_label = f"v{idx+1}"
            filter_parts.append(
                f"[{prev_label}][{input_index}:v]overlay={x}:{y}:enable='between(t,{start},{end})'[{out_label}]"
            )
            prev_label = out_label
            input_index += 1

        filter_complex = ";".join(filter_parts)

        codec, params = self._choose_encoder()
        cmd = [
            "ffmpeg", "-y",
            *ff_inputs,
            "-filter_complex", filter_complex,
            "-map", f"[{prev_label}]",
            "-map", "0:a?",
            "-c:v", codec, *params,
            "-c:a", "aac", "-b:a", "192k",
            "-movflags", "+faststart",
            output_path
        ]

        self._run(cmd)

        # Clean temp images
        self.remove_temp(temp_images)
        return output_path


    def insert_captions(
        self,
        input_path: str,
        captions: list,
        fontfile: Optional[str] = None,
        font: Optional[str] = None,
        fontsize: int = 32,
        fontcolor: str = "white",
        borderw: int = 2,
        bordercolor: str = "black",
        shadowx: int = 2,
        shadowy: int = 2,
        x: int = 0,
        y: int = 0,
        padding_x: int = 10,
        padding_y: int = 10,
        text_align: str = "center",
        output_path: Optional[str] = None
    ) -> str:
        """
        Insert styled captions into a video.

        Parameters
        ----------
        input_path : str
            Path to input video.
        captions : list
            List of dicts, e.g. [{"start": 0.5, "end": 2.1, "text": "Hello"}].
        fontfile : str, optional
            Path to a .ttf/.otf font file.
        font : str, optional
            Font family name (ignored if fontfile provided).
        fontsize : int
            Font size in points.
        fontcolor : str
            Color of the font (e.g. "white", "red@0.8").
        borderw : int
            Width of border outline.
        bordercolor : str
            Border color.
        shadowx : int
            Shadow offset X.
        shadowy : int
            Shadow offset Y.
        x : int
            Horizontal position.
        y : int
            Vertical position.
        output_path : str, optional
            Output video path. If None, a temp file is created.
        """
        if output_path is None: output_path = self._mktemp(".mp4")
        else: os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)

        # Escape special chars for ffmpeg
        def _escape(text: str) -> str:
            return (
                text
                .replace(":", r'\\:')
                .replace(";", "\\;")
                .replace('"', r'\"')
                .replace(",", r"\,")
                .replace("'", "\u2019")
                .replace("%", r"\\\\\%")
                .replace("[", r"\[")
                .replace("]", r"\]")
                .replace("{", r"\{")
                .replace("}", r"\}")
            )
        
        def _pos_x(val):
            if isinstance(val, int):
                return str(val)
            return {
                "left": f"{padding_x}",
                "center": f"(w-text_w)/2",
                "right": f"(w-text_w)-{padding_x}"
            }.get(val, str(val))

        def _pos_y(val):
            if isinstance(val, int):
                return str(val)
            return {
                "top": f"{padding_y}",
                "center": f"(h-text_h)/2",
                "bottom": f"(h-text_h)-{padding_y}"
            }.get(val, str(val))


        drawtext_filters = []
        for cap in captions:
            text = _escape(cap["text"])
            start = cap["start"]
            end = cap["end"]

            font_opts = []
            if fontfile:
                font_opts.append(f"fontfile='{fontfile}'")
            elif font:
                font_opts.append(f"font='{font}'")

            font_opts.extend([
                f'text={text}',
                f"fontsize={fontsize}",
                f"fontcolor={fontcolor}",
                f"borderw={borderw}",
                f"bordercolor={bordercolor}",
                f"shadowx={shadowx}",
                f"shadowy={shadowy}",
                f"x={_pos_x(x)}",
                f"y={_pos_y(y)}",
                f"text_align={text_align}",
                f"enable='between(t,{start},{end})'"
            ])

            drawtext_filters.append("drawtext=" + ":".join(font_opts))

        filter_complex = ",".join(drawtext_filters)

        codec, params = self._choose_encoder()
        cmd = [
            "ffmpeg", "-y",
            "-i", input_path,
            "-filter_complex", filter_complex,
            "-c:v", codec, *params,
            "-c:a", "copy",  # keep original audio, no re-encode
            "-movflags", "+faststart",
            output_path
        ]

        self._run(cmd)
        return output_path


    def change_ratio(
        self,
        input_path: str,
        ratio: str,
        mode: str = "pad",  # "pad" or "crop"
        style: Optional[dict] = None,  # unified style dictionary
        output_path: Optional[str] = None,
        width: Optional[int] = None,
        reencode: bool = True
    ) -> str:
        """
        Change the aspect ratio of the given video with flexible modes.

        Supported ratios:
            - "vertical"       -> 9:16
            - "widescreen"     -> 16:9
            - "ultrawide"      -> 21:9

        Modes:
            - "pad"  -> keep full video, add background (black, blur, or image)
            - "crop" -> fill screen, but cut excess

        Parameters:
        -----------
        input_path : str
            Path to input video file.
        ratio : str
            Target ratio ("vertical", "widescreen", "ultrawide").
        mode : str
            "pad" or "crop" (default: "pad")
        Style dictionary options (only used when mode == "pad"):
            {
                "type": "color" | "blur" | "image",
                # --- for color ---
                "color": "#RRGGBB" or "black"   (default: black)
                # --- for blur ---
                "blur_strength": 20,   # default
                "blur_power": 10,      # default
            }
        output_path : str, optional
            Path to save output. If None, a temp file is created.
        width : int, optional
            Target width (default 1080). Height derived from ratio.
        reencode : bool
            Whether to reencode (True) or try stream copy if not needed.

        Returns:
        --------
        str : path to the converted video.
        """

        # Pick ratio numbers
        if ratio == "vertical":
            target_ratio = (9, 16)
        elif ratio == "widescreen":
            target_ratio = (16, 9)
        elif ratio == "ultrawide":
            target_ratio = (21, 9)
        else:
            raise ValueError("Unsupported ratio. Use 'vertical', 'widescreen', or 'ultrawide'.")

        if width is None:
            width = 1080

        target_w = width
        target_h = int(width * target_ratio[1] / target_ratio[0])

        if output_path is None:
            output_path = self._mktemp(".mp4")
        else:
            os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)

        codec_name, codec_params = self._choose_encoder() if reencode else ("copy", [])

        # Decide ffmpeg filter
        use_complex = False
        if mode == "crop":
            vf = f"scale={target_w}:{target_h}:force_original_aspect_ratio=increase,crop={target_w}:{target_h}"
        elif mode == "pad":

            style = style or {"type": "color", "color": "black"}

            if style["type"] == "color":
                color = style.get("color", "black")

                # Check if color is str and if its black or a valid hex
                if not isinstance(color, str):
                    raise ValueError("Color must be a string (e.g. 'black' or '#RRGGBB').")
                if color.lower() != "black":
                    if not (color.startswith("#") and len(color) == 7 and all(c in "0123456789abcdefABCDEF" for c in color[1:])):
                        raise ValueError("Color must be 'black' or a valid hex string like '#RRGGBB'.")

                if target_w < target_h:
                    vf = f"scale={target_w}:{target_h}:force_original_aspect_ratio=decrease," \
                     f"pad={target_w}:{target_h}:(ow-iw)/2:(oh-ih)/2:{color}"
                else:
                    adjusted_target_w = target_w if target_w % 2 == 0 else target_w - 1
                    adjusted_target_h = target_h if target_h % 2 == 0 else target_h - 1
                    use_complex = False
                    vf = f"scale={adjusted_target_w}:{adjusted_target_h}:force_original_aspect_ratio=decrease,pad={adjusted_target_w}:{adjusted_target_h}:(ow-iw)/2:(oh-ih)/2:{color}"
                    
            elif style["type"] == "blur":
                blur_strength = style.get("blur_strength", 20)
                blur_power = style.get("blur_power", 10)
                blur_strength = blur_strength if isinstance(blur_strength, int) else 20
                blur_power = blur_power if isinstance(blur_power, int) else 10
                use_complex = True
                vf = (
                    f"[0:v]scale={target_w}:{target_h}:force_original_aspect_ratio=increase,crop={target_w}:{target_h},"
                    f"boxblur={blur_strength}:{blur_power}[bg];"
                    f"[0:v]scale={target_w}:{target_h}:force_original_aspect_ratio=decrease[fg];"
                    f"[bg][fg]overlay=(W-w)/2:(H-h)/2"
                )
            else:
                raise ValueError("Invalid style['type']. Must be 'color', 'blur', or 'image'.")
        else:
            raise ValueError("mode must be 'pad' or 'crop'.")

        cmd = [
            "ffmpeg", "-y", "-i", input_path,
        ]

        if use_complex:
            cmd += ["-filter_complex", vf]
        else:
            cmd += ["-vf", vf]

        cmd += [
            "-c:v", codec_name, *codec_params,
            "-c:a", "aac" if reencode else "copy",
            output_path
        ]

        self._run(cmd)
        return output_path
 