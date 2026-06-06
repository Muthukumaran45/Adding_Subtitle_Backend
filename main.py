import whisper
import subprocess
import os
import uuid
import cloudinary
import cloudinary.uploader
from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

app = FastAPI()

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add FFmpeg path (change if needed)
os.environ["PATH"] += os.pathsep + r"C:\ffmpeg\bin"

# Configure Cloudinary
cloudinary.config(
    cloud_name=os.getenv("CLOUDINARY_CLOUD_NAME"),
    api_key=os.getenv("CLOUDINARY_API_KEY"),
    api_secret=os.getenv("CLOUDINARY_API_SECRET"),
)

# Load Whisper model once
model = whisper.load_model("base")


def format_time(seconds):
    hrs = int(seconds // 3600)
    mins = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int((seconds - int(seconds)) * 1000)
    return f"{hrs:02}:{mins:02}:{secs:02},{millis:03}"


@app.post("/generate-subtitles")
async def generate_subtitles(file: UploadFile = File(...)):

    unique_id = str(uuid.uuid4())

    raw_video_path = f"raw_{unique_id}.webm"
    input_video_path = f"input_{unique_id}.mp4"
    audio_path = f"audio_{unique_id}.wav"
    srt_path = f"subtitle_{unique_id}.srt"
    output_video_path = f"output_{unique_id}.mp4"

    try:
        # Save uploaded file
        with open(raw_video_path, "wb") as buffer:
            buffer.write(await file.read())

        # Convert WebM -> MP4
        subprocess.run([
            "ffmpeg",
            "-i", raw_video_path,
            "-c:v", "libx264",
            "-c:a", "aac",
            input_video_path
        ], check=True)

        # Extract audio (best for Whisper)
        subprocess.run([
            "ffmpeg",
            "-i", input_video_path,
            "-vn",
            "-acodec", "pcm_s16le",
            "-ar", "16000",
            "-ac", "1",
            audio_path
        ], check=True)

        # Transcribe using Whisper
        result = model.transcribe(audio_path)

        # Create SRT subtitle file
        with open(srt_path, "w", encoding="utf-8") as f:
            for i, segment in enumerate(result["segments"]):
                start = segment["start"]
                end = segment["end"]
                text = segment["text"]

                f.write(f"{i+1}\n")
                f.write(f"{format_time(start)} --> {format_time(end)}\n")
                f.write(f"{text.strip()}\n\n")

        # Burn subtitles into video
        subprocess.run([
            "ffmpeg",
            "-i", input_video_path,
            "-vf", f"subtitles={srt_path}",
            "-c:a", "copy",
            output_video_path
        ], check=True)

        # Upload video to Cloudinary
        upload_result = cloudinary.uploader.upload(
            output_video_path,
            resource_type="video",
            folder="subtitle_videos"
        )

        video_url = upload_result["secure_url"]

        return {
            "success": True,
            "video_url": video_url
        }

    finally:
        # Clean up temporary files
        for path in [
            raw_video_path,
            input_video_path,
            audio_path,
            srt_path,
            output_video_path
        ]:
            if os.path.exists(path):
                os.remove(path)