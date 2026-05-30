from flask import Flask, render_template, request, jsonify
import os
import subprocess
import json
import pysubs2

app = Flask(__name__)

UPLOAD_FOLDER = "static/uploads"
SUBTITLE_FOLDER = "static/subtitles"
OUTPUT_FOLDER = "static/output"

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(SUBTITLE_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

app.config['MAX_CONTENT_LENGTH'] = 5 * 1024 * 1024 * 1024


# GET AUDIO STREAMS

def get_audio_streams(video_path):

    command = [

        "ffprobe",
        "-v", "error",
        "-select_streams", "a",
        "-show_entries",
        "stream=index:stream_tags=language",
        "-of", "json",
        video_path

    ]

    result = subprocess.run(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )

    data = json.loads(result.stdout)

    return data.get("streams", [])


# GET SUBTITLE STREAMS

def get_subtitle_streams(video_path):

    command = [

        "ffprobe",
        "-v", "error",
        "-select_streams", "s",
        "-show_entries",
        "stream=index:stream_tags=language",
        "-of", "json",
        video_path

    ]

    result = subprocess.run(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )

    data = json.loads(result.stdout)

    return data.get("streams", [])


# EXTRACT SUBTITLE

def extract_subtitle(
    video_path,
    stream_index,
    output_file
):

    command = [

        "ffmpeg",

        "-i", video_path,

        "-map", f"0:{stream_index}",

        output_file,

        "-y"

    ]

    subprocess.run(command)


# CONVERT TO VTT

def convert_to_vtt(
    input_file,
    output_file
):

    subs = pysubs2.load(input_file)

    subs.save(
        output_file,
        format_="vtt"
    )


# CREATE VIDEO WITH SELECTED AUDIO

def create_selected_audio_video(

    video_path,

    audio_index,

    output_path

):

    command = [

        "ffmpeg",

        "-i", video_path,

        "-map", "0:v:0",

        "-map", f"0:a:{audio_index}",

        "-c:v", "copy",

        "-c:a", "copy",

        output_path,

        "-y"

    ]

    subprocess.run(command)


@app.route("/", methods=["GET", "POST"])
def index():

    video_file = None

    output_video = None

    subtitle_tracks = []

    audio_tracks = []

    if request.method == "POST":

        video = request.files.get("video")

        selected_audio = request.form.get("audio_track")

        if video:

            # CLEAR OLD FILES

            for folder in [

                UPLOAD_FOLDER,

                SUBTITLE_FOLDER,

                OUTPUT_FOLDER

            ]:

                for file in os.listdir(folder):

                    os.remove(
                        os.path.join(
                            folder,
                            file
                        )
                    )

            # SAVE VIDEO

            video_path = os.path.join(

                UPLOAD_FOLDER,

                video.filename

            )

            video.save(video_path)

            video_file = video.filename

            # GET AUDIO TRACKS

            audio_streams = get_audio_streams(video_path)

            for i, stream in enumerate(
                audio_streams
            ):

                language = stream.get(

                    "tags",

                    {}

                ).get(

                    "language",

                    f"audio{i}"

                )

                audio_tracks.append({

                    "index": i,

                    "lang": language

                })

            # FIRST TIME ONLY:
            # SHOW TRACKS

            if selected_audio is None:

                return render_template(

                    "index.html",

                    video_uploaded=True,

                    video_file=video_file,

                    audio_tracks=audio_tracks

                )

            # CREATE VIDEO USING
            # SELECTED AUDIO

            output_name = "selected_audio.mp4"

            output_path = os.path.join(

                OUTPUT_FOLDER,

                output_name

            )

            create_selected_audio_video(

                video_path,

                selected_audio,

                output_path

            )

            output_video = output_name

            # SUBTITLE EXTRACTION

            subtitle_streams = get_subtitle_streams(video_path)

            for i, stream in enumerate(

                subtitle_streams

            ):

                language = stream.get(

                    "tags",

                    {}

                ).get(

                    "language",

                    f"sub{i}"

                )

                srt_name = f"{language}_{i}.srt"

                vtt_name = f"{language}_{i}.vtt"

                srt_path    = os.path.join(

                    SUBTITLE_FOLDER,

                    srt_name

                )

                vtt_path = os.path.join(

                    SUBTITLE_FOLDER,

                    vtt_name

                )

                extract_subtitle(

                    video_path,

                    stream["index"],

                    srt_path

                )

                convert_to_vtt(

                    srt_path,

                    vtt_path

                )

                subtitle_tracks.append({

                    "file": vtt_name,

                    "lang": language

                })

    return render_template(

        "index.html",

        output_video=output_video,

        subtitle_tracks=subtitle_tracks,

        audio_tracks=audio_tracks

    )


@app.route("/upload_subtitle", methods=["POST"])
def upload_subtitle():

    subtitle = request.files.get("subtitle")

    input_path = os.path.join(

        SUBTITLE_FOLDER,

        subtitle.filename

    )

    subtitle.save(input_path)

    base_name = os.path.splitext(

        subtitle.filename

    )[0]

    vtt_name = base_name + ".vtt"

    vtt_path = os.path.join(

        SUBTITLE_FOLDER,

        vtt_name

    )

    ext = os.path.splitext(

        subtitle.filename

    )[1].lower()

    if ext != ".vtt":

        convert_to_vtt(

            input_path,

            vtt_path

        )

    return jsonify({

        "file": vtt_name,

        "lang": base_name

    })


if __name__ == "__main__":

    app.run(debug=True)
