# -*- coding: utf-8 -*-

####
# リネームして config.py として利用してください
####

DUP_FRAME = 14
DUP_AUDIO = 500  # ms

# multi processing
MERGE_WORKERS = 2
ENCODE_WORKERS = 1

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
LOG_LEVEL = 'DEBUG'  # DEBUG,INFO,WARN,ERROR,CRITICAL
