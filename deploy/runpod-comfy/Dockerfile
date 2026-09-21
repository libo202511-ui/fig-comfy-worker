# 增量补丁镜像：基于 Docker Hub 上已有的完整镜像，只换 fig 自己的节点补丁层
# 迭代节点 22 时用这个，十几分钟出一版；base 或依赖变了才用 Dockerfile 全量重建
ARG BASE_TAG=5.10.0-gguf-v15
FROM liyouchang111/fig-comfy-worker:${BASE_TAG}

# 覆盖 WanVideoModelLoader 包装层。标记对不上就让构建失败，
# 避免再推出一个"看着是新 tag、里面还是旧补丁"的镜像
COPY zzz_fig_wan_patch /comfyui/custom_nodes/zzz_fig_wan_patch
RUN ZZZ=/comfyui/custom_nodes/zzz_fig_wan_patch/__init__.py \
 && rm -rf /comfyui/custom_nodes/zzz_fig_wan_patch/__pycache__ \
 && test -f "$ZZZ" \
 && grep -q 'FIG_WAN_PATCH=v16' "$ZZZ" \
 && python3 -c "import py_compile,sys; py_compile.compile(sys.argv[1], doraise=True)" "$ZZZ"

# 启动前改磁盘上所有 Wan 加载器的脚本；base 里已把 /start.sh 包过一层，这里只刷新脚本本身
COPY fig_boot_patch.py /fig_boot_patch.py
RUN test -f /start.orig.sh
