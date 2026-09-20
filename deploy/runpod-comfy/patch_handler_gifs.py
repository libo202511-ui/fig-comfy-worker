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
        orig = getattr(execution, "get_input_data", None)
        if orig is None:
            print("FIG_WAN_PATCH=v9 no get_input_data", flush=True)
            return
        if getattr(orig, "_fig_wan_hooked", False):
            print("FIG_WAN_PATCH=v9 already hooked", flush=True)
            return
        modes = [
            "sdpa", "flash_attn_2", "flash_attn_3", "sageattn", "sageattn_3",
            "radial_sage_attention", "sageattn_compiled", "sageattn_ultravico", "comfy",
        ]

        def coerce_mode(val):
            if isinstance(val, str):
                return val
            try:
                return modes[int(val)]
            except Exception:
                return "sdpa"

        def as_str(val, default=""):
            if isinstance(val, str):
                return val
            if val is None:
                return default
            return str(val)

        def hooked(inputs, class_def, *args, **kwargs):
            result = orig(inputs, class_def, *args, **kwargs)
            try:
                if getattr(class_def, "__name__", "") == "WanVideoModelLoader":
                    data = result[0] if isinstance(result, tuple) else result
                    if isinstance(data, dict):
                        if "attention_mode" in data:
                            data["attention_mode"] = [coerce_mode(x) for x in data["attention_mode"]]
                        if "quantization" in data:
                            data["quantization"] = [as_str(x, "disabled") for x in data["quantization"]]
                        if "model" in data:
                            data["model"] = [as_str(x) for x in data["model"]]
                        print("FIG_WAN_PATCH=v9 coerced", data.get("attention_mode"), flush=True)
            except Exception as exc:
                print("FIG_WAN_PATCH=v9 coerce skip", exc, flush=True)
            return result

        hooked._fig_wan_hooked = True
        execution.get_input_data = hooked
        print("FIG_WAN_PATCH=v9 hooked get_input_data", flush=True)
    except Exception as exc:
        print("FIG_WAN_PATCH=v9 hook skip", exc, flush=True)

_fig_link_volume_models()
print("FIG_WAN_PATCH=v9", flush=True)
'''


def inject_volume_links(text: str) -> str:
    """Worker 启动时挂盘符号链接，并注入取参钩子。"""
    if WRAP_MARK in text:
        return text
    return LINK_SNIPPET + "\n" + text


def inject_handler_wrap(text: str) -> str:
    """在 handler(job) 入口挂钩子，此时 Comfy 已经起来。"""
    if re.search(r"^def handler\([^)]*\):\r?\n[ \t]*_fig_wrap_wan_loader\(\)", text, re.M):
        return text
    match = HANDLER_RE.search(text)
    if not match:
        print("WARN: def handler not found")
        return text
    return text[: match.end()] + "    _fig_wrap_wan_loader()\n" + text[match.end() :]


def patch_text(text: str) -> str | None:
    """把 gifs 列表并进 images；对不上官方写法时返回 None。"""
    if 'if "gifs" in node_output' in text:
        return text
    match = IMAGES_RE.search(text)
    if not match:
        return None
    indent = match.group(1)
    insert = (
        f'{indent}if "gifs" in node_output:\n'
        f'{indent}    node_output.setdefault("images", [])\n'
        f'{indent}    node_output["images"].extend(node_output["gifs"])\n'
        f"{match.group(0)}"
    )
    return text[: match.start()] + insert + text[match.end() :]


def main() -> None:
    """扫描并改写 handler；找不到也不抛错，避免挡住 GGUF 镜像构建。"""
    targets = find_targets()
    print("handler candidates:", [str(path) for path in targets])
    patched = 0
    for path in targets:
        try:
            text = path.read_text(encoding="utf-8")
        except OSError as exc:
            print(f"skip {path}: {exc}")
            continue
        if WORKER_MARK not in text:
            print(f"skip {path}: not worker-comfyui")
            continue
        new_text = inject_volume_links(text)
        new_text = inject_handler_wrap(new_text)
        gifs_text = patch_text(new_text)
        if gifs_text is not None:
            new_text = gifs_text
        if new_text == text:
            print(f"already patched {path}")
            patched += 1
            continue
        path.write_text(new_text, encoding="utf-8")
        print(f"patched {path}")
        patched += 1
    if patched == 0:
        print("WARN: handler.py not patched, continue without gifs merge")


if __name__ == "__main__":
    main()
