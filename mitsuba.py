# -*- coding: utf-8 -*-
import ctypes
import os
import shutil
import cv2
import glob
import subprocess
from pydub import AudioSegment
from collections import defaultdict
from tqdm import tqdm
from multiprocessing import Process, Queue, Value, Pipe
from queue import Empty
from logging import getLogger, StreamHandler, Formatter, FileHandler, getLevelName
from config import *


def setup_logger(modname):
    log_level = getLevelName(LOG_LEVEL)
    logger = getLogger(modname)
    logger.setLevel(log_level)

    sh = StreamHandler()
    sh.setLevel(log_level)
    formatter = Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    sh.setFormatter(formatter)
    logger.addHandler(sh)

    fh = FileHandler("error.log")  # fh = file handler
    fh.setLevel(log_level)
    fh_formatter = Formatter(
        '%(asctime)s - %(filename)s - %(name)s - %(lineno)d - %(levelname)s - %(message)s')
    fh.setFormatter(fh_formatter)
    logger.addHandler(fh)
    return logger


logger = setup_logger(__name__)


def merge_video(movie_files, key_name, send_end):
    tmp_video_file = os.path.join(TMP_DIR, f"tmp_v_{key_name}.mp4")
    debug_1 = ""
    try:
        # 形式はmp4
        fourcc = cv2.VideoWriter_fourcc('m', 'p', '4', 'v')
        # fourcc = cv2.VideoWriter_fourcc(*'hev1') #有効だけど、重いかも。
        # fourcc = cv2.VideoWriter_fourcc(*'avc1')

        #動画情報の取得
        movie = cv2.VideoCapture(movie_files[0])
        fps = movie.get(cv2.CAP_PROP_FPS)
        height = movie.get(cv2.CAP_PROP_FRAME_HEIGHT)
        width = movie.get(cv2.CAP_PROP_FRAME_WIDTH)

        # 出力先のファイルを開く
        out = cv2.VideoWriter(tmp_video_file, int(fourcc), fps,
                              (int(width), int(height)))

        for i, movies in enumerate(movie_files):
            debug_1 = movies
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
    except Exception as e:
        logger.error(e)
        logger.error(debug_1)

    out.release()

    send_end.send((tmp_video_file, height))


def merge_audio(movie_files, key_name, send_end):
    tmp_audio_file_sub = os.path.join(TMP_DIR, f"tmp_a_{key_name}_sub.wav")
    tmp_audio_file = os.path.join(TMP_DIR, f"tmp_a_{key_name}.wav")

    audio_merged = AudioSegment.empty()
    for i, movies in enumerate(movie_files):
        command = f"ffmpeg -y -i {movies} -vn -loglevel quiet {tmp_audio_file_sub}"
        subprocess.run(command, shell=True)

        audio_tmp = AudioSegment.from_file(tmp_audio_file_sub, format="wav")

        if i == 0:
            audio_merged += audio_tmp
        else:
            audio_merged += audio_tmp[DUP_AUDIO:]

    # 結合した音声書き出し
    audio_merged.export(tmp_audio_file, format="wav")
    os.remove(tmp_audio_file_sub)
    send_end.send(tmp_audio_file)


def encode_movie(key_name, video_file, height, audio_file):
    filename = os.path.join(TMP_DIR, f"{key_name}.mp4")
    # 動画と音声結合
    vf = VIDEO_FILTER  
    cv = f"-c:v {VIDEO_CODEC}"
    # ビットレートは解像度に応じて固定にしています。
    if height == 1080:  # FHD
        bv = f"-b:v {VIDEO_BR_1}"
    elif height == 720:  # HD
        bv = f"-b:v {VIDEO_BR_2}"
    else:  # VGA
        bv = f"-b:v {VIDEO_BR_3}"

    loglevel = "-loglevel quiet"
    command = f"ffmpeg -y -i {video_file} -i {audio_file} {cv} {bv} {vf} -c:a aac {loglevel} {filename}"
    subprocess.run(command, shell=True)
    os.remove(video_file)
    os.remove(audio_file)


def transfer(tran_q, merge_q, end_sw):
    # ネットワーク越しなどの場合に一旦ローカルにコピーするための処理
    while not end_sw.value:
        try:
            files_list, key_name, _ = tran_q.get(timeout=30)
            files_list_t = []
            for f in files_list:
                if INPUT_FILE_COPY:
                    copy_to_path = os.path.join(TMP_DIR, f.split("/")[-1])
                    if not os.path.exists(copy_to_path):
                        shutil.copy(f, copy_to_path)
                    files_list_t.append(copy_to_path)
                else:
                    files_list_t.append(f)

            merge_q.put((files_list_t ,key_name))
        except Empty:
            continue


def merger(merge_q, encode_q, end_sw):
    while not end_sw.value:
        try:
            files_list, key_name = merge_q.get(timeout=30)
            recv_end_v, send_end_v = Pipe(False)
            recv_end_a, send_end_a = Pipe(False)
            proc_v = Process(target=merge_video, args=(
                files_list, key_name, send_end_v))
            proc_a = Process(target=merge_audio, args=(
                files_list, key_name, send_end_a))
            proc_v.start()
            proc_a.start()
            proc_v.join()
            proc_a.join()

            if INPUT_FILE_COPY:
                for f in files_list:
                    os.remove(f)

            tmp_video_file, height = recv_end_v.recv()
            tmp_audio_file = recv_end_a.recv()
            encode_q.put((key_name, tmp_video_file, height, tmp_audio_file))
        except Empty:
            continue

def encoder(encode_q, tran2_q, end_sw):
    while not end_sw.value:
        try:
            key_name, tmp_video_file, height, tmp_audio_file = encode_q.get(timeout=30)
            encode_movie(key_name, tmp_video_file, height, tmp_audio_file)
            tran2_q.put(key_name)
        except Empty:
            continue


def transfer2(tran2_q, tqdm_q, end_sw):
    while not end_sw.value:
        try:
            key_name = tran2_q.get(timeout=30)
            copy_from_path = os.path.join(TMP_DIR, f"{key_name}.mp4")
            copy_to_path = os.path.join(OUT_DIR, f"{key_name}.mp4")
            try:
                shutil.move(copy_from_path, copy_to_path)
            except Exception as e:
                logger.error(e)
                continue

            tqdm_q.put(key_name)
        except Empty:
            continue


def progress(tqdm_q, size, pcnt, end_sw):
    with tqdm(total=size) as t:
        while size > pcnt.value:
            key_name = tqdm_q.get()
            t.set_description(f"{key_name} finished")
            t.update(1)
            pcnt.value += 1

    end_sw.value = True


if __name__ == '__main__':
    os.makedirs(TMP_DIR, exist_ok=True)
    os.makedirs(OUT_DIR, exist_ok=True)

    tran_q = Queue()
    merge_q = Queue(maxsize=MERGE_WORKERS*4)
    encode_q = Queue(maxsize=ENCODE_WORKERS*4)
    tran2_q = Queue()
    tqdm_q = Queue()
    pcnt = Value(ctypes.c_int)
    pcnt.value = 0
    end_sw = Value(ctypes.c_bool)
    end_sw.value = False

    # ディレクトリ内の動画を：フロント・リアカメラごと、撮影開始時間ごとにまとめる
    files_dict = defaultdict(list)
    for f in glob.glob(os.path.join(IN_DIR, "*", "*.MP4"), recursive=True):
        files_dict["_".join(f.split("/")[-1].split("_")[:2])].append(f)

    data = []
    for i, (key_name, files_list) in enumerate(files_dict.items()):
        if not os.path.exists(os.path.join(OUT_DIR, f"{key_name}.mp4")):
            data.append((sorted(files_list, key=lambda x:x.split("/")[-1]), key_name, i))

    [tran_q.put(q) for q in data]
    proc_tran = Process(target=transfer, args=(tran_q, merge_q, end_sw))
    proc_tran.start()

    proc_merg = [Process(target=merger, args=(merge_q, encode_q, end_sw))
                 for _ in range(MERGE_WORKERS)]
    [p.start() for p in proc_merg]

    proc_enc = [Process(target=encoder, args=(encode_q, tran2_q, end_sw))
                for _ in range(ENCODE_WORKERS)]
    [p.start() for p in proc_enc]

    proc_tran2 = Process(target=transfer2, args=(tran2_q, tqdm_q, end_sw))
    proc_tran2.start()

    proc_tqdm = Process(target=progress, args=(tqdm_q, len(data), pcnt, end_sw))
    proc_tqdm.start()

    proc_tran.join()
    [p.join() for p in proc_merg]
    [p.join() for p in proc_enc]
    proc_tqdm.join()
    proc_tran2.join()
    shutil.rmtree(TMP_DIR)