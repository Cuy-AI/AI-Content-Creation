import os
import subprocess
import tempfile
import shutil
import json
import re
from PIL import Image
from typing import Tuple, Optional, List, Union

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

    def __init__(self, temp_dir: Optional[str] = None, device_selection = "auto"):
        """
        :param temp_dir: optional folder for temporary files. If None, a temp folder is created.
        """
        self.device = device_selection if device_selection in ("auto", "gpu", "cpu") else "auto"
        self._ensure_ffmpeg()
        if temp_dir:
            os.makedirs(temp_dir, exist_ok=True)
            self.temp_dir = temp_dir
            self._own_temp = False
        else:
            self.temp_dir = tempfile.mkdtemp(prefix="veditor_")
            self._own_temp = True
        self._temp_files = set()

    
    # destructor that cleans up temp files if any
    def __del__(self):
        self.cleanup()

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
        if (self.device == "auto" or self.device == "gpu") and _HAS_TORCH and torch.cuda.is_available():
            # NVENC params: tweak as desired
            return "h264_nvenc", ["-preset", "p6", "-rc", "vbr_hq", "-cq", "19"]
        else:
            # CPU x264
            return "libx264", ["-preset", "ultrafast", "-crf", "18", "-threads", str(max(1, os.cpu_count() or 1))]


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

    def get_keyframes(self, input_path):
        """Return keyframe timestamps (seconds) quickly using packet metadata."""
        cmd = [
            "ffprobe", "-v", "error",
            "-select_streams", "v:0",
            "-show_entries", "packet=pts_time,flags",
            "-of", "json",
            input_path
        ]
        result = subprocess.check_output(cmd)
        data = json.loads(result)
        keyframes = []
        for pkt in data.get("packets", []):
            if "K" in pkt.get("flags", "") and "pts_time" in pkt:
                keyframes.append(float(pkt["pts_time"]))
        return keyframes

    

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

        start = max(float(start), 0.0)
        duration = self.get_duration(input_path)
        if end is not None: end = min(float(end), duration)
        else: end = duration

        # ----------------------------------------
        # Helper for nearest keyframe
        def nearest_keyframe_before(keyframes, time):
            return max([k for k in keyframes if k <= time], default=0.0)

        # ----------------------------------------
        if not reencode:
            # Fast cut (keyframe-based, imprecise)
            cmd = [
                "ffmpeg", "-y",
                "-ss", str(start),
                "-to", str(end),
                "-i", input_path,
                "-c", "copy",
                output_path
            ]
        else:
            # Precise cut using keyframe awareness
            keyframes = self.get_keyframes(input_path)
            fast_seek = nearest_keyframe_before(keyframes, start)

            precise_start = start - fast_seek
            precise_end = end - fast_seek

            vcodec, vparams = self._choose_encoder()

            cmd = [
                "ffmpeg", "-y",
                "-ss", str(fast_seek),
                "-i", input_path,
                "-ss", str(precise_start),
                "-to", str(precise_end),
                "-c:v", vcodec,
                *vparams,                     # dynamic encoder parameters
                "-c:a", "aac",
                "-avoid_negative_ts", "1",
                "-fflags", "+genpts",
                output_path
            ]

        self._run(cmd)
        return output_path


    def replace_audios(
        self,
        input_path: str,
        audios: list,
        output_path: Optional[str] = None,
    ) -> str:
        """
        Replace segments of a video's audio with new clips.

        Each element in `audios` is a dict:
            {
                "audio_path": str,
                "start": float,   # in seconds
                "volume": float (optional)
            }

        Behavior:
        - The original video audio is preserved except where replaced.
        - Replacements overwrite only their respective segments.
        - If input video has no audio, silent base is used.
        - Precision guaranteed (frame-level accurate).

        Returns: output_path
        """
        import os, subprocess

        if not isinstance(audios, list):
            raise ValueError("`audios` must be a list of dicts")

        if output_path is None:
            output_path = self._mktemp(".mp4")
        else:
            os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)

        # Sort by start time to process in order
        audios = sorted(audios, key=lambda x: x.get("start", 0.0))

        # Probe audio presence
        probe_cmd = [
            "ffprobe", "-v", "error",
            "-select_streams", "a",
            "-show_entries", "stream=index",
            "-of", "csv=p=0", input_path
        ]
        has_audio = bool(subprocess.run(probe_cmd, capture_output=True, text=True).stdout.strip())

        video_duration = float(self.get_duration(input_path))

        # Prepare ffmpeg input list: video + each new audio
        cmd = ["ffmpeg", "-y", "-i", input_path]
        valid = []
        for entry in audios:
            path = entry.get("audio_path")
            if not path:
                continue
            start = float(entry.get("start", 0.0))
            vol = float(entry.get("volume", 1.0))
            if start >= video_duration:
                continue
            cmd += ["-i", path]
            valid.append((path, start, vol))
        
        if not valid:
            # nothing to replace → copy video
            copy_cmd = ["ffmpeg", "-y", "-i", input_path, "-c", "copy", output_path]
            self._run(copy_cmd)
            return output_path

        # Initialize filters
        filters = []
        segments = []
        last_end = 0.0
        aformat_post = "aresample=48000,aformat=sample_fmts=fltp:sample_rates=48000:channel_layouts=stereo"

        if has_audio:
            base_audio = "[0:a]"
        else:
            # Create silent base and split it for multiple uses
            # Count how many times we'll need the silent audio
            silent_uses = 0
            for i, (path, start, vol) in enumerate(valid, start=1):
                duration_new = float(self.get_duration(path))
                end = min(video_duration, start + duration_new)
                
                # Check if we need segment before
                if i == 1 and start > 0:
                    silent_uses += 1
                elif i > 1 and start > last_end:
                    silent_uses += 1
                
                # Check if we need tail after last
                if i == len(valid) and end < video_duration:
                    silent_uses += 1
                    
                last_end = end
            
            # Reset last_end for actual processing
            last_end = 0.0
            
            # Create silent source and split it into multiple outputs
            split_outputs = "".join([f"[silent{i}]" for i in range(silent_uses)])
            filters.append(
                f"anullsrc=r=48000:cl=stereo:d={video_duration},asetpts=N/SR/TB"
                f",asplit={silent_uses}{split_outputs}"
            )
            
            silent_counter = 0

        # Build timeline segments
        for i, (path, start, vol) in enumerate(valid, start=1):
            duration_new = float(self.get_duration(path))
            end = min(video_duration, start + duration_new)

            # 1. Add original segment before this start (if any gap)
            if start > last_end:
                if has_audio:
                    filters.append(
                        f"{base_audio}atrim={last_end}:{start},asetpts=PTS-STARTPTS,{aformat_post}[seg_pre{i}]"
                    )
                else:
                    filters.append(
                        f"[silent{silent_counter}]atrim={last_end}:{start},asetpts=PTS-STARTPTS,{aformat_post}[seg_pre{i}]"
                    )
                    silent_counter += 1
                segments.append(f"[seg_pre{i}]")

            # 2. Add replacement audio, trimmed and formatted
            filters.append(
                f"[{i}:a]atrim=0:{end - start},asetpts=PTS-STARTPTS,"
                f"{aformat_post},volume={vol}[seg_rep{i}]"
            )
            segments.append(f"[seg_rep{i}]")

            last_end = end

        # 3. Add remaining tail (if any left after last replacement)
        if last_end < video_duration:
            if has_audio:
                filters.append(
                    f"{base_audio}atrim={last_end}:{video_duration},asetpts=PTS-STARTPTS,{aformat_post}[seg_tail]"
                )
            else:
                filters.append(
                    f"[silent{silent_counter}]atrim={last_end}:{video_duration},asetpts=PTS-STARTPTS,{aformat_post}[seg_tail]"
                )
            segments.append("[seg_tail]")

        # Concatenate all segments sequentially
        concat_inputs = "".join(segments)
        filters.append(f"{concat_inputs}concat=n={len(segments)}:v=0:a=1[outa]")

        filter_complex = ";".join(filters)

        # Final command
        cmd += [
            "-filter_complex", filter_complex,
            "-map", "0:v:0",
            "-map", "[outa]",
            "-c:v", "copy",
            "-c:a", "aac", "-b:a", "192k",
            output_path
        ]

        # Execute
        self._run(cmd)
        return output_path




    def mix_audios(
        self,
        input_path: str,
        audios: list,
        output_path: Optional[str] = None,
        start_time: float = 0.0,
    ) -> str:
        """
        Mix (overlay) multiple audios into `input_path`. Each element in `audios`
        is a dict: {"audio_path": str, "start": float, "volume": float (optional)}.

        `start_time` is a global offset added to each element's "start".
        Ensures each audio begins exactly at its requested time (ms precision).
        Handles videos with or without audio.
        """
        # import os
        # import subprocess

        if not isinstance(audios, list):
            raise ValueError("`audios` must be a list of dicts")

        if output_path is None:
            output_path = self._mktemp(".mp4")
        else:
            os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)

        base_offset = float(start_time or 0.0)
        video_duration = float(self.get_duration(input_path))

        # Probe whether input video has audio
        probe_cmd = [
            "ffprobe", "-v", "error",
            "-select_streams", "a",
            "-show_entries", "stream=index",
            "-of", "csv=p=0", input_path
        ]
        has_audio = bool(subprocess.run(probe_cmd, capture_output=True, text=True).stdout.strip())

        # Build ffmpeg command input list (video first, then each audio path)
        cmd = ["ffmpeg", "-y", "-i", input_path]
        valid_audios = []
        for entry in audios:
            if not isinstance(entry, dict) or "audio_path" not in entry:
                continue
            start = float(entry.get("start", 0.0)) + base_offset
            if start >= video_duration:
                # nothing to place (starts after video end)
                continue
            cmd += ["-i", entry["audio_path"]]
            valid_audios.append({
                "audio_path": entry["audio_path"],
                "start": start,
                "volume": float(entry.get("volume", 1.0))
            })

        # If nothing to do:
        if not valid_audios and not has_audio:
            # no new audios and no original audio -> copy video only
            copy_cmd = ["ffmpeg", "-y", "-i", input_path, "-c", "copy", output_path]
            self._run(copy_cmd)
            return output_path
        if not valid_audios and has_audio:
            # no new audios but original audio exists -> copy input
            copy_cmd = ["ffmpeg", "-y", "-i", input_path, "-c", "copy", output_path]
            self._run(copy_cmd)
            return output_path

        # We will create a sequential mixing graph:
        #  - base0 = original audio trimmed OR silent source (if no audiotrack)
        #  - for each new audio i:
        #       del_i = delayed + trimmed + converted audio
        #       base{i} = amix(base{i-1}, del_i)   (normalize=0 to avoid auto attenuation)
        filters = []
        # audio normalization target: stereo 48k FLTP (common, prevents amix format errors)
        aformat_post = "aresample=48000,aformat=sample_fmts=fltp:sample_rates=48000:channel_layouts=stereo"

        # base audio label
        base_label = "base0"
        if has_audio:
            # take original audio, trim to video length and normalize format
            filters.append(
                f"[0:a]atrim=0:{video_duration:.3f},asetpts=PTS-STARTPTS,{aformat_post},volume=1.0[{base_label}]"
            )
        else:
            # no original audio -> create silent track of video duration
            # use anullsrc with same sample rate / layout
            filters.append(
                f"anullsrc=cl=stereo:r=48000,atrim=0:{video_duration:.3f},asetpts=PTS-STARTPTS,{aformat_post}[{base_label}]"
            )

        # Mix audios one by one into base
        # audio input indices are 1..N in the same order we appended "-i" above
        for idx, ainfo in enumerate(valid_audios, start=1):
            delay_ms = int(round(ainfo["start"] * 1000.0))
            vol = ainfo["volume"]
            delayed_label = f"del{idx}"
            next_base = f"base{idx}"

            # build delayed, trimmed, formatted version of this audio
            # :all=1 applies same delay to all channels reliably
            filters.append(
                f"[{idx}:a]adelay={delay_ms}:all=1,atrim=0:{video_duration:.3f},"
                f"asetpts=PTS-STARTPTS,{aformat_post},volume={vol}[{delayed_label}]"
            )

            # amix the running base and the delayed audio -> new base
            # duration=first and normalize=0 (do not automatically attenuate)
            filters.append(
                f"[{base_label}][{delayed_label}]amix=inputs=2:duration=first:normalize=0[{next_base}]"
            )

            base_label = next_base  # for next iteration

        # final alias to outa
        filters.append(f"[{base_label}]anull[outa]")

        filter_complex = ";".join(filters)

        # build final command mapping video + generated audio
        cmd += [
            "-filter_complex", filter_complex,
            "-map", "0:v:0",
            "-map", "[outa]",
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

            # --- Handle image input (PIL or path) ---
            if isinstance(image, Image.Image): # Check for PIL Image object
                tmp_img = self._mktemp(".png")
                image.save(tmp_img)
                image_path = tmp_img
                temp_images.append(tmp_img)
            elif isinstance(image, str):
                image_path = image
            else:
                raise TypeError(f"Invalid image type: {type(image)}")

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



    def insert_images_with_motion(
        self,
        input_path: str,
        images: List[dict],
        rotate_scale_fps: int = 60,
        translation_fps: int = 60,
        output_path: Optional[str] = None
    ) -> str:
        """
        Overlay multiple images with complex motion (translation, rotation, and scaling)
        using FFmpeg time-based expressions.

        The method handles two distinct FPS settings:
        1. `translation_fps`: Controls the frame rate of the base video stream, crucial for 
           the smoothness of X/Y position updates (translation).
        2. `rotate_scale_fps`: Controls the frame rate of the individual image stream, 
           critical for the smoothness of rotation and scale calculations.
        
        Parameters
        ----------
        input_path : str
            Path to the base video on which images will be overlaid.
        images : List[dict]
            List of dictionaries defining images, timing, and motion expressions. 
            Each dictionary must contain "start" and "end" (in seconds) and "image" (PIL.Image or path).
            Optional keys for motion expressions (must use 't' for time):
            - "x": FFmpeg expression for horizontal position (e.g., 'W/2 - w/2 + 50*sin(t)').
            - "y": FFmpeg expression for vertical position (e.g., 'H/2 + 50*cos(t)').
            - "rotate": FFmpeg expression for angle in radians (e.g., 't*0.5').
            - "scale": FFmpeg expression for width:height (e.g., 'iw*(1+0.1*sin(t)):ih*(1+0.1*sin(t))').
            - "time_base": "image" to shift 't' by 'start' (t-start) or "video" (default).
        rotate_scale_fps : int, optional
            The target frame rate for the image stream's rotation and scale calculations. 
            Higher values (e.g., 60, 120) result in smoother rotation/scale animation. Defaults to 60.
        translation_fps : int, optional
            The target frame rate for the base video stream's time base. 
            Higher values (e.g., 60, 120) result in smoother X/Y translation. Defaults to 60.
        output_path : str, optional
            Where to save the final video file.

        Returns
        -------
        str
            Path to the output video file.
        """
        if output_path is None:
            output_path = self._mktemp(".mp4")
        else:
            # Assuming os.makedirs is available
            os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)

        ff_inputs = ["-i", input_path]
        filter_parts = []
        input_index = 1
        prev_label = "0:v" # The base video stream
        temp_images = []

        # --- Helper to replace only standalone t ---
        def safe_t_replace(expr: str, start: float) -> str:
            if not expr:
                return expr
            return re.sub(r'(?<![A-Za-z_])t(?![A-Za-z_])', f'(t-{start})', expr)


        base_video_label = "base_high_fps"
        
        # Force high FPS on the base video and reset its PTS for clean chained evaluation.
        # This is CRITICAL for smooth X/Y motion, which is driven by the base stream's FPS.
        filter_parts.append(
            f"[0:v]fps=fps={translation_fps},setpts=N/({translation_fps}*TB)[{base_video_label}]"
        )
        prev_label = base_video_label


        # --- Loop over all overlay images ---
        for idx, img in enumerate(images):
            start = img["start"]
            end = img["end"]
            image = img["image"]
            time_base = img.get("time_base", "video")

            # --- Handle image input (PIL or path) ---
            if isinstance(image, Image.Image): # Check for PIL Image object
                tmp_img = self._mktemp(".png")
                image.save(tmp_img)
                image_path = tmp_img
                temp_images.append(tmp_img)
            elif isinstance(image, str):
                image_path = image
            else:
                raise TypeError(f"Invalid image type: {type(image)}")
            
            ff_inputs += ["-i", image_path]

            # --- Extract expressions ---
            x_expr = str(img.get("x", "0"))
            y_expr = str(img.get("y", "0"))
            rotate_expr = img.get("rotate")
            scale_expr = img.get("scale")

            # --- Local time shift (must happen before filter chain generation) ---
            if time_base == "image":
                x_expr = safe_t_replace(x_expr, start)
                y_expr = safe_t_replace(y_expr, start)
                if rotate_expr:
                    rotate_expr = safe_t_replace(rotate_expr, start)
                if scale_expr:
                    scale_expr = safe_t_replace(scale_expr, start)

            label_input = f"{input_index}:v"
            steps = []
            

            # --- 1. Prepare Image Stream ---

            # Ensure alpha channel is present for rotation/overlay
            steps.append(f"[{label_input}]format=rgba[alpha{idx}]")
            label_input = f"alpha{idx}"

            # Add a little pad to avoid problems on rotations
            if rotate_expr:
                steps.append(
                    f"[{label_input}]pad=iw*1.05:ih*1.05:(ow-iw)/2:(oh-ih)/2:color=black@0[padded{idx}]"
                )
                label_input = f"padded{idx}"

            # Create a looping stream for the 't' variable to work
            steps.append(
                f"[{label_input}]loop=loop=-1:size=1:start=0[looped{idx}]"
            )
            label_input = f"looped{idx}"

            # Set fps for scale/rptation the motion
            if scale_expr or rotate_expr:
                steps.append(f"[{label_input}]fps=fps={rotate_scale_fps}[fps{idx}]")
                label_input = f"fps{idx}"

            # --- 2. Optional Scale ---
            if scale_expr:
                # Add the mandatory 'eval=frame' to enable dynamic scaling with 't'
                dynamic_scale_expr = f"{scale_expr}:eval=frame" 
                
                steps.append(f"[{label_input}]scale={dynamic_scale_expr}[s{idx}]")
                label_input = f"s{idx}"

            # --- 3. Optional Rotation (Robust) ---
            if rotate_expr:
                steps.append(
                    f"[{label_input}]"
                    f"rotate=a='{rotate_expr}':c=none:ow='hypot(iw,ih)':oh='ow'[rot{idx}]"
                )
                label_input = f"rot{idx}"
                
                
            # --- 4. Overlay motion ---
            out_label = f"v{idx+1}"
            
            # Add 'shortest=1' to the overlay. This is critical for chaining and preventing runaway encoding
            # when a base video is short but the previous stream was implicitly infinite.
            steps.append(
                f"[{prev_label}][{label_input}]overlay="
                f"x='{x_expr}':y='{y_expr}':enable='between(t,{start},{end})':shortest=1[{out_label}]"
            )

            filter_parts.append(";".join(steps))
            prev_label = out_label
            input_index += 1

        # --- Assemble FFmpeg command (No changes here) ---
        filter_complex = ";".join(filter_parts)
        codec, params = self._choose_encoder() # Assuming this handles codec selection

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

        self._run(cmd) # Assuming this executes the command
        self.remove_temp(temp_images) # Assuming this cleans up temp files
        
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
        padding_x: int = 0,
        padding_y: int = 0,
        text_align: str = "center",
        chunk_size: int = 25,
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
                # ⚠️ Keep the replacing order (backslash first)
                .replace("\\", "\\\\\\\\\\\\\\\\\\")
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
                "center": f"((w-text_w)/2)-({padding_x})",
                "right": f"(w-text_w)-({padding_x})"
            }.get(val, str(val))

        def _pos_y(val):
            if isinstance(val, int):
                return str(val)
            return {
                "top": f"{padding_y}",
                "center": f"((h-text_h)/2)-({padding_y})",
                "bottom": f"(h-text_h)-({padding_y})"
            }.get(val, str(val))


        # Split captions into smaller groups
        def _chunks(lst, size):
            for i in range(0, len(lst), size):
                yield lst[i:i + size]

        # initial input
        current_input = input_path

        # perform multiple ffmpeg runs, one per chunk
        for i, chunk in enumerate(_chunks(captions, chunk_size)):
            drawtext_filters = []
            for cap in chunk:
                text = _escape(cap["text"])
                start, end = cap["start"], cap["end"]

                font_opts = []
                if fontfile:
                    font_opts.append(f"fontfile='{fontfile}'")
                elif font:
                    font_opts.append(f"font='{font}'")

                font_opts.extend([
                    f"text={text}",
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

            # Create a temporary intermediate file
            temp_output = (
                output_path if (i == (len(captions)-1) // chunk_size) else self._mktemp(".mp4")
            )

            cmd = [
                "ffmpeg", "-y",
                "-i", current_input,
                "-filter_complex", filter_complex,
                "-c:v", codec, *params,
                "-c:a", "copy",
                "-movflags", "+faststart",
                temp_output,
            ]

            # Run ffmpeg synchronously
            self._run(cmd)

            # Next input = this output
            current_input = temp_output

        return current_input


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
 