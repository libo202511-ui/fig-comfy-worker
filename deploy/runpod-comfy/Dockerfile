# fig Comfy Worker：节点打进镜像，Wan 模型走 Network Volume（/runpod-volume/models）
# 基础镜像与控制台 Hub 的 5.10.0 对齐；不要装 ComfyUI-Manager（会乱升级）
FROM runpod/worker-comfyui:5.10.0-base

# 与 Tkdqqp 手册第 3 步一致（不含 Manager / AdvancedLivePortrait）
RUN comfy-node-install \
    https://github.com/M1kep/ComfyLiterals \
    https://github.com/WASasquatch/was-node-suite-comfyui \
    https://github.com/city96/ComfyUI-GGUF \
    https://github.com/Fannovel16/ComfyUI-Frame-Interpolation \
    https://github.com/ltdrdata/ComfyUI-Inspire-Pack \
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

# GGUF：缺 gguf 包时 nodes.py import 失败，Comfy 只报 Unet Loader (GGUF) not found
# 底包通常没有 git，再 clone 会 127；节点已由上面 comfy-node-install 装好，这里只补 pip
RUN python3 -m pip install --no-cache-dir gguf \
 && (test -f /comfyui/custom_nodes/ComfyUI-GGUF/nodes.py \
     || test -f /comfyui/custom_nodes/comfyui-gguf/nodes.py)

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
