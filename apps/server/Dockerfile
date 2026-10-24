FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
# H5 MediaRecorder 常产出 webm；ASR 前需 ffmpeg 转成 wav
# 国内构建走清华 Debian 镜像（deb.debian.org 在大陆云厂商网络下经常卡死），可用 --build-arg APT_MIRROR 覆盖
ARG APT_MIRROR=mirrors.tuna.tsinghua.edu.cn
RUN sed -i "s/deb.debian.org/${APT_MIRROR}/g; s/security.debian.org/${APT_MIRROR}/g" /etc/apt/sources.list.d/debian.sources \
    && apt-get update && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
# 国内环境默认走清华 PyPI 源，可用 --build-arg PIP_INDEX_URL 覆盖
ARG PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple
RUN pip install --no-cache-dir -i $PIP_INDEX_URL -r requirements.txt
COPY . .
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

