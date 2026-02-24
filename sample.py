import whisper
import subprocess
import os
from moviepy import VideoFileClip

# Tell Whisper/subprocess where ffmpeg is (update this path to yours)
os.environ["PATH"] += os.pathsep + r"C:\ffmpeg\bin"

def format_time(seconds):
    hrs = int(seconds // 3600)
    mins = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int((seconds - int(seconds)) * 1000)
    return f"{hrs:02}:{mins:02}:{secs:02},{millis:03}"

# 1. Load Whisper model
model = whisper.load_model("base")

# 2. Input video
video_path = "input_video.mp4"

# 3. Extract audio from video
video = VideoFileClip(video_path)
audio_path = "audio.wav"
video.audio.write_audiofile(audio_path)
video.close()

# 4. Transcribe audio
result = model.transcribe(audio_path)

# 5. Save subtitles as SRT
srt_path = "subtitles.srt"
with open(srt_path, "w", encoding="utf-8") as f:
    for i, segment in enumerate(result["segments"]):
        start = segment["start"]
        end = segment["end"]
        text = segment["text"]

        f.write(f"{i+1}\n")
        f.write(f"{format_time(start)} --> {format_time(end)}\n")
        f.write(f"{text.strip()}\n\n")

# 6. Burn subtitles into video using FFmpeg
output_video = "output_with_subtitles.mp4"
subprocess.run([
    "ffmpeg",
    "-i", video_path,
    "-vf", f"subtitles={srt_path}",
    output_video
])

print("Done! Subtitled video saved as:", output_video)