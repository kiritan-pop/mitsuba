import os
import shutil
import cv2
import glob
import subprocess
from pydub import AudioSegment
from collections import defaultdict
from tqdm import tqdm, trange
from multiprocessing import Process, Queue, TimeoutError
from queue import Empty

WORKERS = 6
DUP_FRAME = 14
TIMEOUT = 10

def comb_movie(num,name_q):
    while True:
        try:
            movie_files, out_path, *_ = name_q.get(timeout=TIMEOUT)
            os.makedirs("tmp", exist_ok=True)
            os.makedirs("out", exist_ok=True)

            if os.path.exists(os.path.join("out",out_path)):
                continue

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

            audio_merged = None
            for movies in tqdm(movie_files, desc=f"merge_{num:02}", leave=False, position=num*2+1):
                # 動画ファイルの読み込み，引数はビデオファイルのパス
                movie = cv2.VideoCapture(movies)
                count = movie.get(cv2.CAP_PROP_FRAME_COUNT)
                frames = []
                if movie.isOpened() == False:  # 正常に動画ファイルを読み込めたか確認
                    continue

                for _ in trange(int(count), desc=f"  read_{num:02}", leave=False, position=num*2+2):
                    ret, tmp_f = movie.read()  # read():1コマ分のキャプチャ画像データを読み込む
                    if ret:
                        frames.append(tmp_f)

                # 読み込んだフレームを書き込み
                for frame in tqdm(frames[:-DUP_FRAME], desc=f" write_{num:02}", leave=False, position=num*2+2):
                    out.write(frame)

                command = f"ffmpeg -y -i {movies} -vn -loglevel quiet tmp/audio_{num:02}.wav"
                subprocess.run(command, shell=True)

                audio_tmp = AudioSegment.from_file(f"tmp/audio_{num:02}.wav", format="wav")
                audio_tmp = audio_tmp[:-DUP_FRAME/fps*1000]

                if audio_merged is None:
                    audio_merged = audio_tmp
                else:
                    audio_merged += audio_tmp

            # 結合した音声書き出し
            audio_merged.export(f"tmp/audio_merged_{num:02}.wav", format="wav")
            out.release()

            # 動画と音声結合
            vf = ""  #ビデオフィルタはお好みで 例）ややソフト・彩度アップ・ノイズ除去の場合 "-vf smartblur=lr=1:ls=1:lt=0:cr=-0.9:cs=-2:ct=-31,eq=brightness=-0.06:saturation=1.4,hqdn3d,pp=ac"
            # 高速なエンコーダに対応していればお好みで 例）macなら h264_videotoolbox 等 libx264, nvenc
            cv = f"-c:v h264_nvenc"
            # ビットレートは解像度に応じて固定にしています。
            if height == 1080: # FHD
                bv = f"-b:v 11m"
            elif height == 720: # HD
                bv = f"-b:v 6m"
            else: # VGA
                bv = f"-b:v 3m"

            loglevel = "-loglevel quiet"
            command = f"ffmpeg -y -i tmp/video_{num:02}.mp4 -i tmp/audio_merged_{num:02}.wav {cv} {bv} {vf} -c:a aac {loglevel} out/{out_path}"
            subprocess.run(command, shell=True)

        except (TimeoutError, Empty):
            return

if __name__ == '__main__':
    name_q = Queue()

    # ディレクトリ内の動画を：フロント・リアカメラごと、撮影開始時間ごとにまとめる
    files_dict = defaultdict(list)
    for f in glob.glob("./in/*.MP4"):
        files_dict["_".join(f.split("/")[-1].split("_")[:2])].append(f)

    for key_name, files_list in files_dict.items():
        name_q.put((sorted(files_list), key_name+".mp4"))

    p_list = []
    for num in range(WORKERS):
        tmp  = Process(target=comb_movie, args=(num,name_q))
        tmp.start()
        p_list.append(tmp)

    for p in p_list :
        p.join()

    # tmp 削除
    shutil.rmtree('tmp/')
