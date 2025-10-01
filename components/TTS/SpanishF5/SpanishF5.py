import os
import json
import subprocess
import tempfile
import uvicorn
import toml
from pathlib import Path
import shutil

from classes.BaseAI import BaseAI
from classes.Server import Server

class SpanishF5(BaseAI):

    def __init__(self):
        super().__init__()

        self.params_path = "params.json"  # Docker
        self.set_default_params()

    def _create_toml_config(self, gen_text: str, output_path: str) -> str:
        """
        Create a TOML configuration file for F5-TTS inference.
        """
        config = {
            "model": "F5-TTS",
            "ref_audio": self.params.get("ref_audio", ""),
            "ref_text": "",
            "gen_text": gen_text,
            "gen_file": "",
            "remove_silence": self.params.get("remove_silence", False),
            "output_dir": os.path.dirname(output_path)
        }
        
        # Create temporary TOML file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.toml', delete=False, encoding='utf-8') as f:
            toml.dump(config, f)
            return f.name

    def _run_f5_inference(self, toml_path: str) -> tuple[bool, str]:
        """
        Run F5-TTS inference using the CLI command.
        """
        try:
            cmd = ["f5-tts_infer-cli", "-c", toml_path]
            result = subprocess.run(
                cmd, 
                capture_output=True, 
                text=True, 
                check=True,
                timeout=300  # 5 minute timeout
            )
            return True, result.stdout
        except subprocess.CalledProcessError as e:
            error_msg = f"F5-TTS CLI failed with return code {e.returncode}: {e.stderr}"
            return False, error_msg
        except subprocess.TimeoutExpired:
            return False, "F5-TTS inference timed out after 5 minutes"
        except FileNotFoundError:
            return False, "f5-tts_infer-cli command not found. Make sure F5-TTS is installed and available in PATH."
        except Exception as e:
            return False, f"Unexpected error running F5-TTS: {str(e)}"

    def generate(self, prompt: str, save_path: str | None = None) -> dict:
        """
        Generate TTS audio using F5-TTS CLI.
        
        Args:
            prompt: Text to convert to speech
            save_path: Path where to save the generated audio file
            
        Returns:
            Dict containing generation metadata
        """
        if not prompt or not prompt.strip():
            raise ValueError("Prompt cannot be empty")
        
        if not save_path:
            save_path = "volume/output/spanishf5/default_output/output.wav"
        
        # If save_path looks like a file (has an extension), use it directly
        if os.path.splitext(save_path)[1]:
            if os.path.dirname(save_path):
                os.makedirs(os.path.dirname(save_path), exist_ok=True)
            output_path = save_path
        else:
            # treat as directory -> auto-generate a filename
            os.makedirs(save_path, exist_ok=True)
            output_path = os.path.join(save_path, "output.wav")
    
        toml_path = None
        try:
            toml_path = self._create_toml_config(prompt, output_path)
            success, message = self._run_f5_inference(toml_path)
            
            if not success:
                raise RuntimeError(f"F5-TTS generation failed: {message}")
            
            # Check if output file was created
            if not os.path.exists(output_path):
                # Look for generated files in the output directory
                output_dir = os.path.dirname(output_path)
                generated_files = [f for f in os.listdir(output_dir) if f.endswith('.wav')]
                if generated_files:
                    # Move the first generated file to the expected output path
                    shutil.move(os.path.join(output_dir, generated_files[0]), output_path)
                else:
                    raise RuntimeError("F5-TTS completed but no output file was generated")
        finally:
            if toml_path and os.path.exists(toml_path):
                os.unlink(toml_path)
        
        return {
            "prompt": prompt,
            "save_path": output_path,
            **self.get_params()
        }


if __name__ == "__main__":
    spanishf5_server = Server(ai_class=SpanishF5)
    app = spanishf5_server.app
    uvicorn.run(app, host="0.0.0.0", port=8004)