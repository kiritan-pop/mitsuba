# FROM nvidia/cuda:11.3.0-cudnn8-devel-ubuntu20.04
# FROM nvidia/cuda:11.6.2-cudnn8-devel-ubuntu20.04
FROM nvidia/cuda:12.0.1-cudnn8-devel-ubuntu22.04
# FROM nvidia/cuda:12.2.0-devel-ubuntu22.04

ENV DEBIAN_FRONTEND noninteractive

# Python:
RUN apt update && \
    apt install -y \
    python3-dev \
    python3-tk \
    python3-pip \
    python3-numpy

RUN ln -s /usr/bin/python3 /usr/bin/python

RUN pip install --upgrade pip
RUN pip install --upgrade setuptools
RUN pip install pydub tqdm

# OpenCV
RUN apt-get install -y libgl1-mesa-glx libglib2.0-0 libsm6 libxrender1 libxext6 ffmpeg libnvidia-encode-525
RUN pip install "opencv-python<4.8.0"

CMD /bin/bash
