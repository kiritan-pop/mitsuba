import os
import shutil
import cv2
import glob
import subprocess
from pydub import AudioSegment
from collections import defaultdict
from tqdm import tqdm, trange

DUP_FRAME = 14

def comb_movie(movie_files, out_path):

    os.makedirs("tmp", exist_ok=True)
    os.makedirs("out", exist_ok=True)

    # 形式はmp4
    fourcc = cv2.VideoWriter_fourcc('m', 'p', '4', 'v')

    #動画情報の取得
    movie = cv2.VideoCapture(movie_files[0])
    fps = movie.get(cv2.CAP_PROP_FPS)
    height = movie.get(cv2.CAP_PROP_FRAME_HEIGHT)
    width = movie.get(cv2.CAP_PROP_FRAME_WIDTH)

    # 出力先のファイルを開く
    out = cv2.VideoWriter("tmp/video.mp4", int(fourcc), fps,
                          (int(width), int(height)))

    audio_merged = None
    for movies in tqdm(movie_files, desc="merge", leave=False):
        # 動画ファイルの読み込み，引数はビデオファイルのパス
        movie = cv2.VideoCapture(movies)
        count = movie.get(cv2.CAP_PROP_FRAME_COUNT)
        frames = []
        if movie.isOpened() == False:  # 正常に動画ファイルを読み込めたか確認
            continue

        for _ in trange(int(count), desc="read ", leave=False):
            ret, tmp_f = movie.read()  # read():1コマ分のキャプチャ画像データを読み込む
            if ret:
                frames.append(tmp_f)

        # 読み込んだフレームを書き込み
        for frame in tqdm(frames[:-DUP_FRAME], desc="write", leave=False):
          out.write(frame)

        command = f"ffmpeg -y -i {movies} -vn -loglevel quiet tmp/audio.wav"
        subprocess.run(command, shell=True)

        audio_tmp = AudioSegment.from_file("tmp/audio.wav", format="wav")
        audio_tmp = audio_tmp[:-DUP_FRAME/fps*1000]

        if audio_merged is None:
            audio_merged = audio_tmp
        else:
            audio_merged += audio_tmp

    # 結合した音声書き出し
    audio_merged.export("tmp/audio_merged.wav", format="wav")
    out.release()

    # 動画と音声結合
    command = f"ffmpeg -y -i tmp/video.mp4 -i tmp/audio_merged.wav -c:v copy -c:a aac -loglevel quiet out/{out_path}"
    subprocess.run(command, shell=True)

    # tmp 削除
    shutil.rmtree('tmp/')


# ディレクトリ内の動画を：フロント・リアカメラごと、撮影開始時間ごとにまとめる
files_dict = defaultdict(list)
for f in glob.glob("./in/*.MP4"):
    files_dict["_".join(f.split("/")[-1].split("_")[:2])].append(f)

for key_name, files_list in tqdm(files_dict.items(),desc="total"):
    comb_movie(sorted(files_list), key_name+".mp4")
