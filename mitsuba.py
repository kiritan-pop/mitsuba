# -*- coding: utf-8 -*-
import os
import shutil
import cv2
import glob
import subprocess
from pydub import AudioSegment
from collections import defaultdict
from tqdm import tqdm, trange
from multiprocessing import Pool,Process, Queue, TimeoutError
from queue import Empty

DUP_FRAME = 14
DUP_AUDIO = 400 #ms

# multi processing
WORKERS = 3
TIMEOUT = 10

def comb_movie(movie_files, out_path, num):
    # 作成済みならスキップ
    if os.path.exists(os.path.join("out",out_path)):
        return

    # 形式はmp4
    fourcc = cv2.VideoWriter_fourcc('m', 'p', '4', 'v')

    #動画情報の取得
    movie = cv2.VideoCapture(movie_files[0])
    fps = movie.get(cv2.CAP_PROP_FPS)
    height = movie.get(cv2.CAP_PROP_FRAME_HEIGHT)
    width = movie.get(cv2.CAP_PROP_FRAME_WIDTH)

    # 出力先のファイルを開く
    out = cv2.VideoWriter(f"tmp/video_{num:02}.mp4", int(fourcc), fps,
                        (int(width), int(height)))

    # audio_merged = None
    audio_merged = AudioSegment.empty()
    for i, movies in enumerate(movie_files):
        # 動画ファイルの読み込み，引数はビデオファイルのパス
        movie = cv2.VideoCapture(movies)
        count = movie.get(cv2.CAP_PROP_FRAME_COUNT)
        frames = []
        if movie.isOpened() == False:  # 正常に動画ファイルを読み込めたか確認
            continue

        for _ in range(int(count)):
            ret, tmp_f = movie.read()  # read():1コマ分のキャプチャ画像データを読み込む
            if ret:
                frames.append(tmp_f)

        # 読み込んだフレームを書き込み
        if i == 0:
            [out.write(f) for f in frames]
        else:
            [out.write(f) for f in frames[DUP_FRAME:]]

        command = f"ffmpeg -y -i {movies} -vn -loglevel quiet tmp/audio_{num:02}.wav"
        subprocess.run(command, shell=True)

        audio_tmp = AudioSegment.from_file(f"tmp/audio_{num:02}.wav", format="wav")

        if i == 0:
            audio_merged += audio_tmp
        else:
            audio_merged += audio_tmp[DUP_AUDIO:]

    # 結合した音声書き出し
    audio_merged.export(f"tmp/audio_merged_{num:02}.wav", format="wav")
    out.release()

    # 動画と音声結合
    vf = ""  #ビデオフィルタはお好みで 例）ややソフト・彩度アップ・ノイズ除去の場合 "-vf smartblur=lr=1:ls=1:lt=0:cr=-0.9:cs=-2:ct=-31,eq=brightness=-0.06:saturation=1.4,hqdn3d,pp=ac"
    # 高速なエンコーダに対応していればお好みで 例）macなら h264_videotoolbox 等 libx264, h264_nvenc
    cv = f"-c:v h264_videotoolbox"
    # ビットレートは解像度に応じて固定にしています。
    if height == 1080: # FHD
        bv = f"-b:v 5m"
    elif height == 720: # HD
        bv = f"-b:v 3m"
    else: # VGA
        bv = f"-b:v 1m"

    loglevel = "-loglevel quiet"
    command = f"ffmpeg -y -i tmp/video_{num:02}.mp4 -i tmp/audio_merged_{num:02}.wav {cv} {bv} {vf} -c:a aac {loglevel} out/{out_path}"
    subprocess.run(command, shell=True)


def wrapper(args):
    comb_movie(*args)

if __name__ == '__main__':
    os.makedirs("./tmp", exist_ok=True)
    os.makedirs("./out", exist_ok=True)

    # ディレクトリ内の動画を：フロント・リアカメラごと、撮影開始時間ごとにまとめる
    files_dict = defaultdict(list)
    for f in glob.glob("./in/*.MP4"):
        files_dict["_".join(f.split("/")[-1].split("_")[:2])].append(f)

    data = []
    for i, (key_name, files_list) in enumerate(files_dict.items()):
        data.append((sorted(files_list), key_name+".mp4", i))

    p = Pool(WORKERS)
    with tqdm(total=len(data)) as t:
        for _ in p.imap_unordered(wrapper, data):
            t.update(1)
    # tmp 削除
    shutil.rmtree('./tmp/')
