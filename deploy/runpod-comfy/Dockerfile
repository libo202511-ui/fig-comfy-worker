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
# comfy-node-install 成功也不等于能加载；这里再装依赖，目录没有就补 clone，没有 nodes.py 则构建失败
RUN set -eux; \
    NODE_DIR=""; \
    for d in /comfyui/custom_nodes/ComfyUI-GGUF /comfyui/custom_nodes/comfyui-gguf; do \
      if [ -d "$d" ]; then NODE_DIR="$d"; break; fi; \
    done; \
    if [ -z "$NODE_DIR" ]; then \
      git clone --depth 1 https://github.com/city96/ComfyUI-GGUF.git /comfyui/custom_nodes/ComfyUI-GGUF; \
      NODE_DIR=/comfyui/custom_nodes/ComfyUI-GGUF; \
    fi; \
    pip install --no-cache-dir -r "$NODE_DIR/requirements.txt"; \
    test -f "$NODE_DIR/nodes.py"; \
    ls -la /comfyui/custom_nodes | head -n 50

# 覆盖官方路径表，让盘上的 diffusion_models / text_encoders 也能被扫到
COPY extra_model_paths.yaml /comfyui/extra_model_paths.yaml
COPY extra_model_paths.yaml /extra_model_paths.yaml

# 官方 handler 只回 images，VHS 视频在 gifs 键会被丢掉
COPY patch_handler_gifs.py /tmp/patch_handler_gifs.py
RUN python3 /tmp/patch_handler_gifs.py
