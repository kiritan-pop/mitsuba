# -*- coding: utf-8 -*-

####
# リネームして config.py として利用してください
####

# 重複量（変更不要）
DUP_FRAME = 14
DUP_AUDIO = 461  # ms

# 並列実行数
MERGE_WORKERS = 2
ENCODE_WORKERS = 1

# ファイルコピー（ネットワーク越しのファイルを変換する場合等）
INPUT_FILE_COPY = False

# dir
TMP_DIR = "tmp/"
IN_DIR = "in/"
OUT_DIR = "out/"

# ffmpeg encode option
VIDEO_FILTER = ""  # ビデオフィルタはお好みで 例）ややソフト・彩度アップ・ノイズ除去の場合 "-vf smartblur=lr=1:ls=1:lt=0:cr=-0.9:cs=-2:ct=-31,eq=brightness=-0.06:saturation=1.4,hqdn3d,pp=ac"
VIDEO_CODEC = "libx264"  # macなら h264_videotoolbox 等 libx264, h264_nvenc
VIDEO_BR_1 = "5m" # 1080p
VIDEO_BR_2 = "3m" # 720p
VIDEO_BR_3 = "1m" # 480p

# log
LOG_LEVEL = 'INFO'  # DEBUG,INFO,WARN,ERROR,CRITICAL
