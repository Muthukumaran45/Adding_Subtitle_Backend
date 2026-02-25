import whisper
import subprocess
import os
import uuid
import cloudinary
import cloudinary.uploader
from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from moviepy import VideoFileClip
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

app = FastAPI()

# CORS
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

    input_video_path = f"temp_{unique_id}.mp4"
    audio_path = f"temp_{unique_id}.wav"
    srt_path = f"temp_{unique_id}.srt"
    output_video_path = f"output_{unique_id}.mp4"

    try:
        # Save uploaded video
        with open(input_video_path, "wb") as buffer:
            buffer.write(await file.read())

        # Extract audio
        video = VideoFileClip(input_video_path)
        video.audio.write_audiofile(audio_path)
        video.close()

        # Transcribe
        result = model.transcribe(audio_path)

        # Create SRT
        with open(srt_path, "w", encoding="utf-8") as f:
            for i, segment in enumerate(result["segments"]):
                start = segment["start"]
                end = segment["end"]
                text = segment["text"]

                f.write(f"{i+1}\n")
                f.write(f"{format_time(start)} --> {format_time(end)}\n")
                f.write(f"{text.strip()}\n\n")

        # Burn subtitles
        subprocess.run([
            "ffmpeg",
            "-i", input_video_path,
            "-vf", f"subtitles={srt_path}",
            "-c:a", "copy",
            output_video_path
        ], check=True)

        # Upload to Cloudinary
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
        # Cleanup temp files
        for path in [input_video_path, audio_path, srt_path, output_video_path]:
            if os.path.exists(path):
                os.remove(path)