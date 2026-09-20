"""把 worker-comfyui handler 里 VHS 的 gifs 输出并进 images，否则数字人 mp4 会被丢掉。"""
from __future__ import annotations

import re
from pathlib import Path

# 只认官方 worker 的 handler，避免误改 ComfyUI 自带 handler.py
WORKER_MARK = "worker-comfyui"
IMAGES_RE = re.compile(r'^([ \t]*)if\s+"images"\s+in\s+node_output\s*:', re.M)
HANDLER_RE = re.compile(r"^(def handler\([^)]*\):\r?\n)", re.M)
CANDIDATES = (
    Path("/handler.py"),
    Path("/comfyui/handler.py"),
    Path("/rp_handler.py"),
    Path("/workspace/handler.py"),
    Path("/src/handler.py"),
    Path("/src/rp_handler.py"),
)


def _unique_files(paths: list[Path]) -> list[Path]:
    """按绝对路径去重，保持原顺序。"""
    seen: set[str] = set()
    result: list[Path] = []
    for path in paths:
        key = str(path.resolve()) if path.exists() else str(path)
        if key in seen:
            continue
        seen.add(key)
        result.append(path)
    return result


def find_targets() -> list[Path]:
    """定位官方 worker-comfyui 的 handler.py。"""
    found = [path for path in CANDIDATES if path.is_file()]
    extras: list[Path] = []
    for path in Path("/").glob("**/handler.py"):
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        if WORKER_MARK in text and 'if "images" in node_output' in text:
            extras.append(path)
    return _unique_files(found + extras)


WRAP_MARK = "_fig_wrap_wan_loader"
LINK_SNIPPET = '''
def _fig_link_volume_models():
    import os
    import shutil
    pairs = (
        ("/runpod-volume/models/liveportrait", "/comfyui/models/liveportrait"),
        ("/runpod-volume/models/insightface", "/comfyui/models/insightface"),
    )
    for src, dest in pairs:
        try:
            if os.path.lexists(dest):
                if os.path.islink(dest) or os.path.isfile(dest):
                    os.remove(dest)
                elif os.path.isdir(dest):
                    shutil.rmtree(dest)
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            os.symlink(src, dest)
            print("fig linked", dest, "->", src)
        except OSError as exc:
            print("fig link skip", dest, exc)

def _fig_wrap_wan_loader():
    """任务进来时再钩 execution.get_input_data，不扫 sys.modules、不 getattr torch.classes。"""
    try:
        import execution
        orig =
