# CL-Splats (ICCV 2025) の実行環境。RTX 5070 Ti (compute capability 12.0) は CUDA 12.8 以上が必要。
FROM nvidia/cuda:12.8.1-devel-ubuntu24.04

ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        git python3 python3-venv python3-dev build-essential ninja-build \
        libgl1 libglib2.0-0 ca-certificates \
    && rm -rf /var/lib/apt/lists/*

RUN python3 -m venv /opt/venv
ENV PATH=/opt/venv/bin:$PATH

# PyTorch は CL-Splats より先に入れる（CUDA 12.8 版）。
RUN pip install --no-cache-dir torch==2.7.1 torchvision==0.22.1 \
    --index-url https://download.pytorch.org/whl/cu128

ARG CLSPLATS_COMMIT=587fffc207f9c7cbb348f35e6d1d223d007eab69
RUN git clone https://github.com/jan-ackermann/cl-splats.git /opt/cl-splats \
    && git -C /opt/cl-splats checkout ${CLSPLATS_COMMIT}
WORKDIR /opt/cl-splats
RUN pip install --no-cache-dir -e '.[train,gsplat]' huggingface_hub

# gsplat の CUDA カーネルは初回に JIT でコンパイルされる（イメージの作成時は GPU がない）。
ENV TORCH_CUDA_ARCH_LIST=12.0
ENV WANDB_MODE=disabled

# run.sh は --user で非 root として動かす。/root/.cache をマウントして HOME に使う。
RUN chmod 755 /root
ENV HOME=/root/.cache/home
