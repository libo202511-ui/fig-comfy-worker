# 增量构建 fig Comfy Worker：基于 Docker Hub 已有的完整镜像只叠补丁层
# 需仓库 Secrets：DOCKERHUB_USERNAME、DOCKERHUB_TOKEN
name: fig-comfy-worker-patch

on:
  workflow_dispatch:
    inputs:
      base_tag:
        description: 基础镜像 tag（Docker Hub 上已有的完整镜像）
        default: 5.10.0-gguf-v18
      out_tag:
        description: 产出镜像 tag（填到 RunPod Endpoint 的就是它）
        default: 5.10.0-gguf-v19
      patch_mark:
        description: 补丁标记（对不上就让构建失败，避免推出旧补丁）
        default: FIG_WAN_PATCH=v17

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - name: 把空闲盘挂到 Docker
        uses: easimon/maximize-build-space@v10
        with:
          root-reserve-mb: 8192
          temp-reserve-mb: 100
          swap-size-mb: 8192
          remove-dotnet: true
          remove-android: true
          remove-haskell: true
          remove-codeql: true
          remove-docker-images: true
          build-mount-path: /var/lib/docker

      - name: 重启 Docker
        run: |
          sudo service docker restart
          df -h

      - uses: actions/checkout@v4

      - name: 生成增量 Dockerfile
        run: |
          cd deploy/runpod-comfy
          cat > Dockerfile.patch <<'EOF'
          ARG BASE_TAG
          FROM liyouchang111/fig-comfy-worker:${BASE_TAG}
          COPY patch_handler_gifs.py /tmp/patch_handler_gifs.py
          RUN python3 /tmp/patch_handler_gifs.py
          ARG PATCH_MARK
          COPY zzz_fig_wan_patch /comfyui/custom_nodes/zzz_fig_wan_patch
          COPY fig_boot_patch.py /fig_boot_patch.py
          RUN ZZZ=/comfyui/custom_nodes/zzz_fig_wan_patch/__init__.py; \
           rm -rf /comfyui/custom_nodes/zzz_fig_wan_patch/__pycache__; \
           if [ ! -f "$ZZZ" ]; then echo "FAIL 补丁文件没进镜像"; exit 1; fi; \
           echo "镜像内标记：$(grep -m1 FIG_MARK "$ZZZ")"; \
           echo "流程要求：$PATCH_MARK"; \
           if ! grep -q "$PATCH_MARK" "$ZZZ"; then \
             echo "FAIL 标记不符，GitHub 上那份补丁不是这个版本"; exit 1; fi; \
           if ! python3 -c "import py_compile,sys; py_compile.compile(sys.argv[1], doraise=True)" "$ZZZ"; then \
             echo "FAIL 补丁文件语法错误，多半被网页编辑器折断了"; exit 1; fi
          RUN pip install --no-cache-dir "protobuf>=6.31.1" \
           && python3 -c "import google.protobuf as p; print('protobuf', p.__version__)" \
           && python3 -c "import onnx; print('onnx', onnx.__version__)" \
           && python3 -c "import onnxruntime as o; print('onnxruntime', o.__version__)" \
           && python3 -c "import insightface as i; print('insightface', i.__version__)" \
           && (python3 -c "import mediapipe as m; print('mediapipe', m.__version__)" \
               || echo "mediapipe 不可用，若有节点依赖它需回看 protobuf 版本")
          RUN if [ ! -f /start.orig.sh ] && [ -f /start.sh ]; then \
             cp /start.sh /start.orig.sh \
             && printf '%s\n' '#!/bin/bash' 'python3 /fig_boot_patch.py || true' \
                'exec /start.orig.sh "$@"' > /start.sh \
             && chmod +x /start.sh /start.orig.sh; \
           fi; \
           ls -l /start.sh /start.orig.sh
          EOF
          cat Dockerfile.patch

      - uses: docker/setup-buildx-action@v3

      - uses: docker/login-action@v3
        with:
          username: ${{ secrets.DOCKERHUB_USERNAME }}
          password: ${{ secrets.DOCKERHUB_TOKEN }}

      - uses: docker/build-push-action@v6
        with:
          context: deploy/runpod-comfy
          file: deploy/runpod-comfy/Dockerfile.patch
          push: true
          build-args: |
            BASE_TAG=${{ inputs.base_tag }}
            PATCH_MARK=${{ inputs.patch_mark }}
          tags: liyouchang111/fig-comfy-worker:${{ inputs.out_tag }}
          provenance: false
          sbom: false
