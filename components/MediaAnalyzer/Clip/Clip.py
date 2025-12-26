import cv2
import torch
from PIL import Image
from transformers import CLIPProcessor, CLIPModel

import uvicorn
from classes.BaseAI import BaseAI
from classes.Server import Server

class Clip:
    def __init__(self, model_name: str = "openai/clip-vit-base-patch32"):
        """
        Loads the CLIP model and processor.
        """
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        print(f"Clip: Loading model to {self.device}...")
        
        # Load the model and the processor (handles both images and text)
        self.model = CLIPModel.from_pretrained(model_name).to(self.device)
        self.processor = CLIPProcessor.from_pretrained(model_name)


    def predict(self, image_path: str, labels: list):
        """
        Executes inference on a single image against a list of labels.
        """
        # Load and convert image
        image = Image.open(image_path).convert("RGB")

        # Preprocess inputs
        inputs = self.processor(
            text=labels, 
            images=image, 
            return_tensors="pt", 
            padding=True
        ).to(self.device)

        # Forward pass
        with torch.no_grad():
            outputs = self.model(**inputs)

        # Get the similarity scores (logits_per_image is the similarity score)
        logits_per_image = outputs.logits_per_image 
        probs = logits_per_image.softmax(dim=1)  # Convert to probabilities

        # Format results
        results = {labels[i]: probs[0][i].item() for i in range(len(labels))}
        return results
    


    def predict_video_frame(self, video_path: str, labels: list, timestamp_seconds: float):
        """
        Jump to a specific second in a video and perform inference on that single frame.
        """
        cap = cv2.VideoCapture(video_path)
        
        # Convert seconds to milliseconds for OpenCV
        timestamp_ms = timestamp_seconds * 1000
        cap.set(cv2.CAP_PROP_POS_MSEC, timestamp_ms)
        
        ret, frame = cap.read()
        cap.release()

        if not ret:
            raise ValueError(f"Could not read frame at {timestamp_seconds}s. Ensure timestamp is within video duration.")

        # Convert OpenCV BGR to RGB PIL Image
        color_converted = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        pil_image = Image.fromarray(color_converted)

        # CLIP Inference
        inputs = self.processor(
            text=labels, 
            images=pil_image, 
            return_tensors="pt", 
            padding=True
        ).to(self.device)

        with torch.no_grad():
            outputs = self.model(**inputs)
        
        probs = outputs.logits_per_image.softmax(dim=1)[0]
        
        return {
            "timestamp_s": timestamp_seconds,
            "predictions": {labels[i]: probs[i].item() for i in range(len(labels))}
        }



    def predict_video_intervals(self, video_path: str, labels: list, interval_seconds: float):
        """
        Analyzes a video at specific time intervals.
        """
        
        cap = cv2.VideoCapture(video_path)
        fps = cap.get(cv2.CAP_PROP_FPS)
        # Calculate frame skip count
        frame_interval = int(fps * interval_seconds)
        
        video_results = []
        frame_count = 0
        
        while cap.isOpened():
            ret, frame = cap.read()
            if not ret: break
            
            # Process only frames at the specified interval
            if frame_count % frame_interval == 0:
                timestamp = frame_count / fps
                
                # Convert OpenCV BGR to RGB PIL Image
                color_coverted = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                pil_image = Image.fromarray(color_coverted)
                
                # Perform inference
                inputs = self.processor(
                    text=labels, 
                    images=pil_image, 
                    return_tensors="pt", 
                    padding=True
                ).to(self.device)

                with torch.no_grad():
                    outputs = self.model(**inputs)
                
                probs = outputs.logits_per_image.softmax(dim=1)[0]
                
                video_results.append({
                    "timestamp_s": round(timestamp, 2),
                    "predictions": {labels[i]: probs[i].item() for i in range(len(labels))}
                })
            
            frame_count += 1
            
        cap.release()
        return video_results
    

if __name__ == "__main__":
    clip_server = Server(ai_class=Clip)
    app = clip_server.app
    uvicorn.run(app, host="0.0.0.0", port=8005)
    