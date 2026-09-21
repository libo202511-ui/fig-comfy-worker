# fig Comfy Worker：节点打进镜像，Wan 模型走 Network Volume（/runpod-volume/models）
# 基础镜像与控制台 Hub 的 5.10.0 对齐；不要装 ComfyUI-Manager（会乱升级）
FROM runpod/worker-comfyui:5.10.0-base

# 与 Tkdqqp 手册第 3 步一致（不含 Manager；ALP 用下面 148 魔改包，不要 git clone 官方）
RUN comfy-node-install \
    https://github.com/M1kep/ComfyLiterals \
    https://github.com/WASasquatch/was-node-suite-comfyui \
    https://github.com/city96/ComfyUI-GGUF \
    https://github.com/Fannovel16/ComfyUI-Frame-Interpolation \
    https://github.com/ltdrdata/ComfyUI-Inspire-Pack \
    https://github.com/ltdrdata/ComfyUI-Impact-Pack \
    https://github.com/ltdrdata/ComfyUI-Impact-Subpack \
    https://github.com/cubiq/ComfyUI_essentials \
    https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite \
    https://github.com/1038lab/ComfyUI-RMBG \
    https://github.com/yolain/ComfyUI-Easy-Use \
    https://github.com/kijai/ComfyUI-WanVideoWrapper \
    https://github.com/rgthree/rgthree-comfy \
    https://github.com/pythongosssss/ComfyUI-Custom-Scripts \
    https://github.com/zhangp365/ComfyUI-utils-nodes \
    https://github.com/fssorc/ComfyUI_FaceShaper \
    https://github.com/Artificial-Sweetener/comfyui-WhiteRabbit \
    https://github.com/Smirnov75/ComfyUI-mxToolkit \
    https://github.com/kijai/ComfyUI-KJNodes \
    https://github.com/SeanScripts/ComfyUI-Unload-Model

# 插帧节点默认 requirements 会拉 cupy，Serverless 用无 cupy 那份
RUN if [ -f /comfyui/custom_nodes/ComfyUI-Frame-Interpolation/requirements-no-cupy.txt ]; then \
      pip install --no-cache-dir -r /comfyui/custom_nodes/ComfyUI-Frame-Interpolation/requirements-no-cupy.txt; \
    fi \
 && pip install --no-cache-dir insightface onnxruntime-gpu

# GGUF / WanVideoWrapper：comfy-node-install 成功也不等于能 import
# 缺 gguf/accelerate/peft 时整包加载失败，Comfy 只报节点 not found；底包没有 git，不要再 clone
RUN python3 -m pip install --no-cache-dir \
      gguf ftfy accelerate einops diffusers peft sentencepiece protobuf pyloudnorm opencv-python scipy \
 && (test -f /comfyui/custom_nodes/ComfyUI-GGUF/nodes.py \
     || test -f /comfyui/custom_nodes/comfyui-gguf/nodes.py) \
 && (test -f /comfyui/custom_nodes/ComfyUI-WanVideoWrapper/nodes_model_loading.py \
     || test -f /comfyui/custom_nodes/comfyui-wanvideowrapper/nodes_model_loading.py)

# 写实 v1/v2/v3 + 其余节点包：缺依赖时整包 import 失败，Comfy 只报节点 not found
# 扫一遍已装节点的 requirements（跳过插帧会拉 cupy 的那份）；不强制升级 torch
RUN python3 -m pip install --no-cache-dir \
      matplotlib cachetools webcolors opencv-python-headless imageio-ffmpeg \
 && for f in /comfyui/custom_nodes/*/requirements.txt; do \
      case "$f" in \
        *Frame-Interpolation*) continue ;; \
      esac; \
      python3 -m pip install --no-cache-dir --upgrade-strategy only-if-needed -r "$f"; \
    done \
 && (test -f /comfyui/custom_nodes/ComfyUI-Inspire-Pack/inspire/image_util.py \
     || test -f /comfyui/custom_nodes/comfyui-inspire-pack/inspire/image_util.py) \
 && (test -d /comfyui/custom_nodes/ComfyUI-Impact-Pack \
     || test -d /comfyui/custom_nodes/comfyui-impact-pack) \
 && (test -d /comfyui/custom_nodes/ComfyUI-VideoHelperSuite \
     || test -d /comfyui/custom_nodes/comfyui-videohelpersuite) \
 && (test -d /comfyui/custom_nodes/ComfyUI-Easy-Use \
     || test -d /comfyui/custom_nodes/comfyui-easy-use) \
 && (test -d /comfyui/custom_nodes/comfyui-WhiteRabbit \
     || test -d /comfyui/custom_nodes/ComfyUI-WhiteRabbit) \
 && (test -d /comfyui/custom_nodes/ComfyUI-RMBG \
     || test -d /comfyui/custom_nodes/comfyui-rmbg) \
 && (test -d /comfyui/custom_nodes/ComfyUI-mxToolkit \
     || test -d /comfyui/custom_nodes/comfyui-mxtoolkit) \
 && (test -d /comfyui/custom_nodes/ComfyUI-KJNodes \
     || test -d /comfyui/custom_nodes/comfyui-kjnodes) \
 && (test -d /comfyui/custom_nodes/rgthree-comfy) \
 && (test -d /comfyui/custom_nodes/ComfyUI-Custom-Scripts \
     || test -d /comfyui/custom_nodes/comfyui-custom-scripts)

# 148 魔改 ALP：官方包没有 ExpressionEditor_batch / _V2，必须用这份 tar，禁止再 clone 官方
# 路径用短变量，避免 GitHub 网页编辑器把长行使断导致 grep 找不到文件
COPY alp-batch.tgz /tmp/alp-batch.tgz
RUN cd /comfyui/custom_nodes \
 && rm -rf ComfyUI-AdvancedLivePortrait \
 && tar -xzf /tmp/alp-batch.tgz \
 && rm /tmp/alp-batch.tgz \
 && ALP=ComfyUI-AdvancedLivePortrait \
 && test -f "$ALP/nodes.py" \
 && python3 -m pip install --no-cache-dir -r "$ALP/requirements.txt" \
 && grep -q 'class ExpressionEditor_batch' "$ALP/nodes.py" \
 && grep -q 'class ExpressionEditor_batch_V2' "$ALP/nodes.py"

# v4/v5/v6 attention_mode=sageattn：在 loadmodel 入口强制 sdpa，工作流不用改
# GitHub 构建机没有 nvcc，编不了 SageAttention2；用 SDPA 顶同名接口
COPY install_sageattn_shim.py /tmp/install_sageattn_shim.py
RUN python3 -m pip uninstall -y sageattention || true \
 && python3 /tmp/install_sageattn_shim.py \
 && python3 -c "from sageattention import sageattn" \
 && cd /comfyui/custom_nodes \
 && (grep -q FIG_WAN_V12 ComfyUI-WanVideoWrapper/nodes_model_loading.py \
     || grep -q FIG_WAN_V12 comfyui-wanvideowrapper/nodes_model_loading.py)

# 覆盖官方路径表，让盘上的 diffusion_models / text_encoders / liveportrait 也能被扫到
COPY extra_model_paths.yaml /comfyui/extra_model_paths.yaml
COPY extra_model_paths.yaml /extra_model_paths.yaml

# FaceShaper 写死 /comfyui/models/liveportrait；底包若已有同名目录，ln 会链进目录里而不是替换
RUN rm -rf /comfyui/models/liveportrait /comfyui/models/insightface \
 && mkdir -p /comfyui/models \
 && ln -sfn /runpod-volume/models/liveportrait /comfyui/models/liveportrait \
 && ln -sfn /runpod-volume/models/insightface /comfyui/models/insightface

# 官方 handler 只回 images，VHS 视频在 gifs 键会被丢掉；对不上也不让构建失败
COPY patch_handler_gifs.py /tmp/patch_handler_gifs.py
RUN python3 /tmp/patch_handler_gifs.py || echo "WARN: gifs patch skipped"

# FaceShaper 的 insightface 走 onnx，onnx 按 protobuf 6.31.1 生成；
# 上面那轮节点 requirements 会把运行时压到 5.29.6，protobuf 要求运行时不低于生成版本。
# 必须放在所有 pip 之后，否则又被压回去
RUN pip install --no-cache-dir "protobuf>=6.31.1" \
 && python3 -c "import google.protobuf as p; print('protobuf', p.__version__)" \
 && python3 -c "import onnx; print('onnx', onnx.__version__)" \
 && python3 -c "import onnxruntime as o; print('onnxruntime', o.__version__)" \
 && python3 -c "import insightface as i; print('insightface', i.__version__)"

# zzz_ 前缀：Comfy 在 WanVideoWrapper 之后加载，改 NODE_CLASS_MAPPINGS，不依赖 handler 注入
COPY zzz_fig_wan_patch /comfyui/custom_nodes/zzz_fig_wan_patch
RUN ZZZ=/comfyui/custom_nodes/zzz_fig_wan_patch/__init__.py \
 && test -f "$ZZZ" \
 && grep -q 'FIG_WAN_PATCH=v17' "$ZZZ"

# Comfy 起来之前改磁盘上所有 Wan 加载器（镜像 + 盘）。挂盘后才能改到 volume 上的副本
COPY fig_boot_patch.py /fig_boot_patch.py
RUN if [ -f /start.sh ]; then \
      cp /start.sh /start.orig.sh \
      && printf '%s\n' '#!/bin/bash' 'python3 /fig_boot_patch.py || true' 'exec /start.orig.sh "$@"' > /start.sh \
      && chmod +x /start.sh /start.orig.sh; \
    fi
