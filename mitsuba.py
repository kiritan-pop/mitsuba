# -*- coding: utf-8 -*-
import os
import shutil
import cv2
import glob
import subprocess
from pydub import AudioSegment
from collections import defaultdict
from tqdm import tqdm
from multiprocessing import Process, Queue
from queue import Empty

DUP_FRAME = 14
DUP_AUDIO = 400 #ms

# multi processing
MERGE_WORKERS = 4
ENCODE_WORKERS = 2
TIMEOUT = 600

def merge_movie(movie_files, key_name):
    tmp_video_file = os.path.join("tmp", f"tmp_v_{key_name}.mp4")
    tmp_audio_file_sub = os.path.join("tmp", f"tmp_a_{key_name}_sub.wav")
    tmp_audio_file = os.path.join("tmp", f"tmp_a_{key_name}.wav")

    # 形式はmp4
    fourcc = cv2.VideoWriter_fourcc('m', 'p', '4', 'v')

    #動画情報の取得
    movie = cv2.VideoCapture(movie_files[0])
    fps = movie.get(cv2.CAP_PROP_FPS)
    height = movie.get(cv2.CAP_PROP_FRAME_HEIGHT)
    width = movie.get(cv2.CAP_PROP_FRAME_WIDTH)

    # 出力先のファイルを開く
    out = cv2.VideoWriter(tmp_video_file, int(fourcc), fps,
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

        command = f"ffmpeg -y -i {movies} -vn -loglevel quiet {tmp_audio_file_sub}"
        subprocess.run(command, shell=True)

        audio_tmp = AudioSegment.from_file(tmp_audio_file_sub, format="wav")

        if i == 0:
            audio_merged += audio_tmp
        else:
            audio_merged += audio_tmp[DUP_AUDIO:]

    # 結合した音声書き出し
    audio_merged.export(tmp_audio_file, format="wav")
    out.release()
    os.remove(tmp_audio_file_sub)

    # print(f"mergeg {tmp_video_file}/{tmp_audio_file}")
    return tmp_video_file, tmp_audio_file, key_name, fps, height, width


def encode_movie(video_file, audio_file, key_name, fps, height, width):
    filename = os.path.join("out", f"{key_name}.mp4")
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
    command = f"ffmpeg -y -i {video_file} -i {audio_file} {cv} {bv} {vf} -c:a aac {loglevel} {filename}"
    subprocess.run(command, shell=True)
    os.remove(video_file)
    os.remove(audio_file)

    # print(f"encoded {filename}")
    return filename


def merger(merge_q, encode_q):
    try:
        while True:
            files_list, key_name, _ = merge_q.get(timeout=10)
            encode_q.put((merge_movie(files_list, key_name)))
    except Empty:
        return

def encoder(encode_q, t):
    try:
        while True:
            tmp_video_file, tmp_audio_file, key_name, fps, height, width, * \
                _ = encode_q.get(timeout=300)
            encode_movie(tmp_video_file, tmp_audio_file,
                         key_name, fps, height, width)
            t.set_description(key_name)
            t.update(1)
    except Empty:
        return


# def wrapper(args):
#     comb_movie(*args)

if __name__ == '__main__':
    os.makedirs("./tmp", exist_ok=True)
    os.makedirs("./out", exist_ok=True)

    merge_q = Queue()
    encode_q = Queue(maxsize=100)

    # ディレクトリ内の動画を：フロント・リアカメラごと、撮影開始時間ごとにまとめる
    files_dict = defaultdict(list)
    for f in glob.glob("./in/*.MP4"):
        files_dict["_".join(f.split("/")[-1].split("_")[:2])].append(f)

    data = []
    for i, (key_name, files_list) in enumerate(files_dict.items()):
        if not os.path.exists(os.path.join("out", f"{key_name}.mp4")):
            data.append((sorted(files_list), key_name, i))

    [merge_q.put(q) for q in data]

    with tqdm(total=len(data)) as t:
        proc_merg = [Process(target=merger, args=(merge_q, encode_q)) for _ in range(MERGE_WORKERS)]
        [p.start() for p in proc_merg]

        proc_enc = [Process(target=encoder, args=(encode_q, t)) for _ in range(ENCODE_WORKERS)]
        [p.start() for p in proc_enc]

        [p.join() for p in proc_merg]
        [p.join() for p in proc_enc]

    # p = Pool(WORKERS)
    # with tqdm(total=len(data)) as t:
    #     for _ in p.imap_unordered(wrapper, data):
    #         t.update(1)
    # tmp 削除
    shutil.rmtree('./tmp/')
