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
COPY alp-batch.tgz /tmp/alp-batch.tgz
RUN rm -rf /comfyui/custom_nodes/ComfyUI-AdvancedLivePortrait \
 && tar -xzf /tmp/alp-batch.tgz -C /comfyui/custom_nodes \
 && rm /tmp/alp-batch.tgz \
 && python3 -m pip install --no-cache-dir -r /comfyui/custom_nodes/ComfyUI-AdvancedLivePortrait/requirements.txt \
 && grep -q 'class ExpressionEditor_batch' /comfyui/custom_nodes/Co
