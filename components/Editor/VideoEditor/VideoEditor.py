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

# Pillow for image handling (insert_image)
try:
    from PIL import Image
    _HAS_PIL = True
except Exception:
    _HAS_PIL = False


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

    def _run(self, cmd: List[str]):
        print("Running:", cmd)
        proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
        if proc.returncode != 0:
            raise RuntimeError(f"ffmpeg/ffprobe command failed:\n{' '.join(cmd)}\nSTDOUT:\n{proc.stdout}\nSTDERR:\n{proc.stderr}")
        return proc.stdout

    def _mktemp(self, suffix: str = ".mp4") -> str:
        fd, path = tempfile.mkstemp(suffix=suffix, dir=self.temp_dir)
        os.close(fd)
        self._temp_files.add(path)
        return path

    def _probe(self, path: str) -> dict:
        cmd = ["ffprobe", "-v", "error", "-print_format", "json", "-show_format", "-show_streams", path]
        out = self._run(cmd)
        return json.loads(out)

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

    def remove_temp(self, paths: Union[str, List[str]]):
        """
        Remove one temp path or list of paths. If path is in tracked temp files, remove from set.
        """
        if isinstance(paths, str):
            paths = [paths]
        for p in paths:
            try:
                if os.path.exists(p):
                    os.remove(p)
                if p in self._temp_files:
                    self._temp_files.remove(p)
            except Exception:
                pass

    def list_temp(self) -> List[str]:
        """Return list of tracked temp files."""
        return list(self._temp_files)

    def cleanup(self):
        """Remove all tracked temp files and optionally temp dir created by this instance."""
        for p in list(self._temp_files):
            try:
                if os.path.exists(p):
                    os.remove(p)
            except Exception:
                pass
            self._temp_files.discard(p)
        if self._own_temp and os.path.isdir(self.temp_dir):
            try:
                shutil.rmtree(self.temp_dir)
            except Exception:
                pass

    # -------------------
    # Core operations
    # -------------------
    # def insert_image(self,
    #                  input_path: str,
    #                  image: Union[str, 'PIL.Image.Image'],
    #                  start: float,
    #                  end: float,
    #                  position: Tuple[Optional[int], Optional[int]] = (None, None),
    #                  center: bool = True,
    #                  output_path: Optional[str] = None) -> str:
    #     """
    #     Overlay an image (PIL.Image or path) on top of input_path between start and end.
    #     position: (x,y) in pixels; if both None and center True, centers overlay.
    #     Returns output_path.
    #     """
    #     if not _HAS_PIL and not isinstance(image, str):
    #         raise RuntimeError("Pillow is required to pass a PIL.Image. Install pillow or pass an image path.")

    #     # prepare overlay image path
    #     if isinstance(image, str):
    #         overlay_path = image
    #     else:
    #         overlay_path = self._mktemp(suffix=".png")
    #         image.save(overlay_path)

    #     if output_path is None:
    #         output_path = self._mktemp(".mp4")
    #     else:
    #         os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)

    #     enable = f"between(t,{start},{end})"
    #     if position[0] is None and position[1] is None and center:
    #         x_expr = "(main_w-overlay_w)/2"
    #         y_expr = "(main_h-overlay_h)/2"
    #     else:
    #         x_expr = str(int(position[0] or 0))
    #         y_expr = str(int(position[1] or 0))

    #     vf = f"overlay=x={x_expr}:y={y_expr}:enable='{enable}'"

    #     codec, ff_params = self._choose_encoder()
    #     cmd = [
    #         "ffmpeg", "-y", "-i", input_path, "-i", overlay_path,
    #         "-filter_complex", vf,
    #         "-map", "0:a?", "-c:a", "aac", "-b:a", "192k",
    #         "-c:v", codec, *ff_params,
    #         output_path
    #     ]
    #     self._run(cmd)
    #     self._temp_files.add(output_path)
    #     return output_path

    def insert_image(self,
                    input_path: str,
                    image: Union[str, 'PIL.Image.Image'],
                    start: float,
                    end: float,
                    position: Tuple[Optional[int], Optional[int]] = (None, None),
                    center: bool = True,
                    output_path: Optional[str] = None) -> str:
        """
        Overlay an image (PIL.Image or path) on top of input_path between start and end.
        position: (x,y) in pixels; if both None and center True, centers overlay.
        Returns output_path.
        """
        if not _HAS_PIL and not isinstance(image, str):
            raise RuntimeError("Pillow is required to pass a PIL.Image. Install pillow or pass an image path.")

        # prepare overlay image path
        if isinstance(image, str):
            overlay_path = image
        else:
            overlay_path = self._mktemp(suffix=".png")
            image.save(overlay_path)

        if output_path is None:
            output_path = self._mktemp(".mp4")
        else:
            os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)

        enable = f"between(t,{start},{end})"
        if position[0] is None and position[1] is None and center:
            x_expr = "(main_w-overlay_w)/2"
            y_expr = "(main_h-overlay_h)/2"
        else:
            x_expr = str(int(position[0] or 0))
            y_expr = str(int(position[1] or 0))

        vf = f"overlay=x={x_expr}:y={y_expr}:enable='{enable}'"

        # pick encoder: try GPU first
        codec, ff_params = self._choose_encoder()

        cmd = [
            "ffmpeg", "-y",
            # "-hwaccel", "cuda",        # hardware acceleration
            "-i", input_path,
            "-i", overlay_path,
            "-filter_complex", vf,
            "-map", "0:v:0",           # take video
            "-map", "0:a?",            # keep audio if exists
            "-c:v", codec, *ff_params,
            "-c:a", "aac", "-b:a", "192k",
            "-threads", "0",           # let ffmpeg auto decide
            "-shortest",               # stop at shortest stream
            output_path
        ]

        cmd = [
            "ffmpeg", "-y", "-i", input_path, "-i", overlay_path,
            "-filter_complex", vf,
            "-map", "0:a?", "-c:a", "aac", "-b:a", "192k",
            "-c:v", codec, *ff_params,
            "-shortest",               # stop at shortest stream
            "-threads", "0",           # let ffmpeg auto decide
            output_path
        ]

        self._run(cmd)
        self._temp_files.add(output_path)
        return output_path


    def insert_video(self,
                     input_path: str,
                     overlay_path: str,
                     start: float = 0.0,
                     position: Tuple[Optional[int], Optional[int]] = (None, None),
                     center: bool = True,
                     keep_overlay_audio: bool = False,
                     output_path: Optional[str] = None) -> str:
        """
        Overlay another video (overlay_path) on top of input_path, starting at `start` seconds.
        By default overlay audio is ignored and base audio is preserved; set keep_overlay_audio=True to mix overlay audio.
        """
        if output_path is None:
            output_path = self._mktemp(".mp4")
        else:
            os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)

        # Determine overlay duration
        ov_meta = self._probe(overlay_path)
        ov_dur = float(ov_meta.get("format", {}).get("duration") or next((s.get("duration") for s in ov_meta.get("streams", []) if s.get("codec_type")=="video"), 0.0))

        enable = f"between(t,{start},{start + ov_dur})"
        if position[0] is None and position[1] is None and center:
            x_expr = "(main_w-overlay_w)/2"
            y_expr = "(main_h-overlay_h)/2"
        else:
            x_expr = str(int(position[0] or 0))
            y_expr = str(int(position[1] or 0))

        # offset overlay video timestamps
        vf = f"[1:v]setpts=PTS-STARTPTS+{start}/TB[ovl];[0:v][ovl]overlay={x_expr}:{y_expr}:enable='{enable}'"

        codec, ff_params = self._choose_encoder()

        # If keep_overlay_audio True, mix overlay audio with base audio; else keep base audio only
        if keep_overlay_audio:
            # mix audio: [0:a][1:a] amerge / amix
            filter_complex = vf + ";[0:a][1:a]amix=inputs=2:duration=longest:dropout_transition=2[aout]"
            cmd = [
                "ffmpeg", "-y", "-i", input_path, "-i", overlay_path,
                "-filter_complex", filter_complex,
                "-map", "0:v", "-map", "[aout]",
                "-c:v", codec, *ff_params,
                "-c:a", "aac", "-b:a", "192k",
                output_path
            ]
        else:
            # keep base audio
            cmd = [
                "ffmpeg", "-y", "-i", input_path, "-i", overlay_path,
                "-filter_complex", vf,
                "-map", "0:a?", "-c:a", "aac", "-b:a", "192k",
                "-c:v", codec, *ff_params,
                output_path
            ]

        self._run(cmd)
        self._temp_files.add(output_path)
        return output_path

    def mute_audio(self, input_path: str, start: Optional[float] = None, end: Optional[float] = None,
                   output_path: Optional[str] = None) -> str:
        """
        Mute audio entirely (start is None) or between start and end seconds.
        """
        if output_path is None:
            output_path = self._mktemp(".mp4")
        else:
            os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)

        if start is None:
            # remove audio track
            cmd = ["ffmpeg", "-y", "-i", input_path, "-c:v", "copy", "-an", output_path]
            self._run(cmd)
        else:
            if end is None:
                end = self.get_duration(input_path)
            af = f"volume=enable='between(t,{start},{end})':volume=0"
            codec, ff_params = self._choose_encoder()
            cmd = [
                "ffmpeg", "-y", "-i", input_path,
                "-af", af,
                "-c:v", codec, *ff_params,
                "-c:a", "aac", "-b:a", "192k",
                output_path
            ]
            self._run(cmd)
        self._temp_files.add(output_path)
        return output_path

    def replace_audio(self, input_path: str, audio_path: str, output_path: Optional[str] = None) -> str:
        """
        Replace the audio track of input_path with audio_path. Output duration is shortest (use -shortest).
        """
        if output_path is None:
            output_path = self._mktemp(".mp4")
        else:
            os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)

        codec, ff_params = self._choose_encoder()
        cmd = [
            "ffmpeg", "-y", "-i", input_path, "-i", audio_path,
            "-map", "0:v", "-map", "1:a",
            "-c:v", codec, *ff_params,
            "-c:a", "aac", "-b:a", "192k",
            "-shortest", output_path
        ]
        self._run(cmd)
        self._temp_files.add(output_path)
        return output_path

    def merge_audio(self, input_path: str, audio_path: str, start: float = 0.0, output_path: Optional[str] = None) -> str:
        """
        Mix the existing video's audio with another audio, starting the new audio at `start` seconds.
        """
        if output_path is None:
            output_path = self._mktemp(".mp4")
        else:
            os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)

        delay_ms = int(round(start * 1000))
        # double value for stereo channels (adelay expects one value per channel)
        # using same delay for both channels
        adelay_arg = f"{delay_ms}|{delay_ms}"
        ff_filter = f"[1:a]adelay={adelay_arg}[a1];[0:a][a1]amix=inputs=2:duration=longest:dropout_transition=2[aout]"
        codec, ff_params = self._choose_encoder()
        cmd = [
            "ffmpeg", "-y", "-i", input_path, "-i", audio_path,
            "-filter_complex", ff_filter,
            "-map", "0:v", "-map", "[aout]",
            "-c:v", codec, *ff_params,
            "-c:a", "aac", "-b:a", "192k",
            output_path
        ]
        self._run(cmd)
        self._temp_files.add(output_path)
        return output_path

    def change_speed_segment(self,
                             input_path: str,
                             start: float,
                             end: float,
                             speed: float,
                             output_path: Optional[str] = None) -> str:
        """
        Change playback speed for a specific segment (start..end) by factor `speed` (>0).
        The output file will be re-encoded but uses ffmpeg only and concat to stitch parts.
        """
        dur = self.get_duration(input_path)
        start = max(0.0, float(start))
        end = min(float(end), dur)
        if end <= start:
            raise ValueError("end must be > start")

        # Build parts: pre, mid, post
        parts = []
        if start > 0:
            parts.append(("pre", 0.0, start))
        parts.append(("mid", start, end))
        if end < dur:
            parts.append(("post", end, dur))

        temp_parts = []
        codec, ff_params = self._choose_encoder()

        def _build_atempo_chain(factor: float) -> Optional[str]:
            if factor <= 0:
                raise ValueError("speed must be >0")
            factors = []
            rem = factor
            # break into 2 or 0.5 factors until within [0.5,2]
            while rem > 2.0:
                factors.append(2.0)
                rem /= 2.0
            while rem < 0.5:
                factors.append(0.5)
                rem *= 2.0
            factors.append(rem)
            parts = [f"atempo={f:.6f}" for f in factors if abs(f - 1.0) > 1e-9]
            if not parts:
                return None
            return ",".join(parts)

        for tag, s, e in parts:
            out_part = self._mktemp(".mp4")
            if tag == "mid":
                atempo_chain = _build_atempo_chain(speed)
                # adjust video pts: setpts=PTS/<speed>
                vf = f"setpts=PTS/{speed}"
                if atempo_chain:
                    cmd = [
                        "ffmpeg", "-y", "-ss", str(s), "-to", str(e), "-i", input_path,
                        "-filter:v", vf,
                        "-filter:a", atempo_chain,
                        "-c:v", codec, *ff_params,
                        "-c:a", "aac", "-b:a", "192k",
                        out_part
                    ]
                else:
                    cmd = [
                        "ffmpeg", "-y", "-ss", str(s), "-to", str(e), "-i", input_path,
                        "-filter:v", vf,
                        "-c:v", codec, *ff_params,
                        "-c:a", "aac", "-b:a", "192k",
                        out_part
                    ]
                self._run(cmd)
            else:
                # pre/post: re-encode to match codec/params for concat safety
                cmd = [
                    "ffmpeg", "-y", "-ss", str(s), "-to", str(e), "-i", input_path,
                    "-c:v", codec, *ff_params,
                    "-c:a", "aac", "-b:a", "192k",
                    out_part
                ]
                self._run(cmd)
            temp_parts.append(out_part)

        # Concat the parts
        listfile = self._mktemp(suffix=".txt")
        with open(listfile, "w", encoding="utf-8") as f:
            for p in temp_parts:
                f.write(f"file '{os.path.abspath(p)}'\n")

        out_final = output_path or self._mktemp(".mp4")
        cmd = ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", listfile, "-c", "copy", out_final]
        self._run(cmd)
        # register temp files
        self._temp_files.update(temp_parts)
        self._temp_files.add(listfile)
        self._temp_files.add(out_final)
        return out_final


    def cut(self, input_path, start, end, output_path=None, reencode=False):
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
        if output_path is None:
            output_path = self._mktemp(".mp4")
        else:
            os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)

        codec = ["-c", "copy"] if not reencode else ["-c:v", "libx264", "-c:a", "aac"]

        cmd = [
            "ffmpeg", "-y",
            "-ss", str(start),
            "-to", str(end),
            "-i", input_path,
            *codec,
            output_path
        ]

        self._run(cmd)
        return output_path


    def set_captions(
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
        x: str = "(w-text_w)/2",  # default: centered horizontally
        y: str = "h-(text_h*2)",  # default: near bottom
        output_path: Optional[str] = None
    ) -> str:
        """
        Burn captions into the video using ffmpeg drawtext.
        captions: list of dicts [{"start": float, "end": float, "text": str}, ...]
        Styling: fontfile OR font (system font), fontsize, fontcolor, borderw/color, shadow, position.
        """
        if output_path is None:
            output_path = self._mktemp(".mp4")
        else:
            os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)

        draw_filters = []
        for cap in captions:
            start = cap["start"]
            end = cap["end"]
            text = cap["text"].replace(":", r'\:').replace("'", r"\'")  # escape
            enable = f"between(t,{start},{end})"

            style_parts = [
                f"text='{text}'",
                f"fontsize={fontsize}",
                f"fontcolor={fontcolor}",
                f"x={x}",
                f"y={y}",
                f"borderw={borderw}",
                f"bordercolor={bordercolor}",
                f"shadowx={shadowx}",
                f"shadowy={shadowy}",
                f"enable='{enable}'"
            ]
            if fontfile:
                style_parts.append(f"fontfile='{fontfile}'")
            elif font:
                style_parts.append(f"font='{font}'")

            draw_filters.append("drawtext=" + ":".join(style_parts))

        vf = ",".join(draw_filters)
        codec, ff_params = self._choose_encoder()
        cmd = [
            "ffmpeg", "-y", "-i", input_path,
            "-vf", vf,
            "-c:v", codec, *ff_params,
            "-c:a", "aac", "-b:a", "192k",
            output_path
        ]
        self._run(cmd)
        self._temp_files.add(output_path)
        return output_path
