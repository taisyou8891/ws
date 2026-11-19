# GS-ICP SLAM (ECCV 2024, arXiv 2403.12550) の実行環境。
# RTX 5070 Ti (compute capability 12.0) は CUDA 12.8 以上が必要。
FROM nvidia/cuda:12.8.1-devel-ubuntu24.04

ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        git python3 python3-venv python3-dev build-essential ninja-build cmake \
        libgl1 libglib2.0-0 ca-certificates \
    && rm -rf /var/lib/apt/lists/*
# fast_gicp が使う Eigen と PCL。依存が 630 個・600 MB ほどあり、ミラーが 1 個ずつだと遅いので、
# 先に 16 並列で /var/cache/apt/archives に落としてからインストールする（4 つの層に分ける）。
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && apt-get install -y --no-install-recommends --print-uris libeigen3-dev libpcl-dev \
        | sed -n "s/^'\(http[^']*\)'.*/\1/p" > /tmp/uris.txt \
    && wc -l /tmp/uris.txt
RUN sed -n 1,170p /tmp/uris.txt | xargs -P 16 -n 1 curl -fsS --retry 3 -O --output-dir /var/cache/apt/archives
RUN sed -n 171,340p /tmp/uris.txt | xargs -P 16 -n 1 curl -fsS --retry 3 -O --output-dir /var/cache/apt/archives
RUN sed -n 341,510p /tmp/uris.txt | xargs -P 16 -n 1 curl -fsS --retry 3 -O --output-dir /var/cache/apt/archives
RUN tail -n +511 /tmp/uris.txt | xargs -P 16 -n 1 curl -fsS --retry 3 -O --output-dir /var/cache/apt/archives
RUN apt-get install -y --no-install-recommends libeigen3-dev libpcl-dev \
    && rm -rf /var/lib/apt/lists/* /tmp/uris.txt

RUN python3 -m venv /opt/venv
ENV PATH=/opt/venv/bin:$PATH

# PyTorch は GS-ICP SLAM より先に入れる（CUDA 12.8 版）。
RUN pip install --no-cache-dir torch==2.7.1 torchvision==0.22.1 \
    --index-url https://download.pytorch.org/whl/cu128

# CUDA の拡張はイメージの作成時（GPU なし）にコンパイルする。
ENV TORCH_CUDA_ARCH_LIST=12.0

ARG GSICP_COMMIT=5f996a872a979406b270fe0ee3b0a8f25c5e9ae3
RUN git clone --recursive https://github.com/Lab-of-AI-and-Robotics/GS_ICP_SLAM.git /opt/gs_icp_slam \
    && git -C /opt/gs_icp_slam checkout ${GSICP_COMMIT} \
    && git -C /opt/gs_icp_slam submodule update --init --recursive
WORKDIR /opt/gs_icp_slam

RUN pip install --no-cache-dir -r requirements.txt wheel 'setuptools<80' pybind11

# 新しい CUDA・コンパイラで通すための最小限の修正（README に一覧がある）。
# 1. rasterizer のヘッダに <cstdint> を足す（uint32_t などが未定義になる）。
RUN for f in submodules/diff-gaussian-rasterization/cuda_rasterizer/rasterizer_impl.h \
             submodules/diff-gaussian-rasterization/cuda_rasterizer/rasterizer_impl.cu \
             submodules/diff-gaussian-rasterization/cuda_rasterizer/backward.h \
             submodules/diff-gaussian-rasterization/cuda_rasterizer/forward.h; do \
        [ -f "$f" ] && sed -i '1i #include <cstdint>' "$f"; \
    done; \
    sed -i '1i #include <cfloat>' submodules/simple-knn/simple_knn.cu; \
    sed -i '1i #include <cstdint>' submodules/simple-knn/simple_knn.cu; \
    true

RUN pip install --no-cache-dir --no-build-isolation submodules/diff-gaussian-rasterization
RUN pip install --no-cache-dir --no-build-isolation submodules/simple-knn

# 2. fast_gicp 同梱の pybind11 は古く、Python 3.12 で PyFrameObject が不完全型になりコンパイルできない。
#    同梱のものを pybind11 v2.13.6 に差し替える。
RUN rm -rf submodules/fast_gicp/thirdparty/pybind11 \
    && git clone --depth 1 --branch v2.13.6 https://github.com/pybind/pybind11.git submodules/fast_gicp/thirdparty/pybind11

RUN cd submodules/fast_gicp && python setup.py install

# 3. 上流の requirements.txt に matplotlib がないので足す（utils/traj_utils.py が読む）。
RUN pip install --no-cache-dir matplotlib
# 4. numpy 2 で np.unicode_ が無くなっているので np.str_ に直す（utils/traj_utils.py）。
RUN sed -i 's/np\.unicode_/np.str_/g' utils/traj_utils.py
# 5. numpy 2 では np.linalg.inv に torch のテンソルを渡すとテンソルが返り、.transpose() が失敗する
#    （mp_Mapper.py の calc_2d_metric）。先に np.asarray で ndarray にする。
RUN sed -i 's/^\( *\)c2w = final_poses\[i\]$/\1c2w = np.asarray(final_poses[i])/' mp_Mapper.py
# 6. numpy 2 では np.linalg.linalg が無い。np.linalg.svd に直す（mp_Tracker.py・mp_Tracker_unlimit.py の ATE の計算）。
RUN sed -i 's/np\.linalg\.linalg\.svd/np.linalg.svd/' mp_Tracker.py mp_Tracker_unlimit.py

# run.sh は --user で非 root として動かす。
RUN chmod 755 /root
RUN mkdir -m 1777 /tmp/home
ENV HOME=/tmp/home
