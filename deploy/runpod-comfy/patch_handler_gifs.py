"""把 worker-comfyui handler 里 VHS 的 gifs 并进 images，并在失败 JSON 里带上节点 22 入参诊断。"""
from __future__ import annotations

import re
from pathlib import Path

WORKER_MARK = "worker-comfyui"
IMAGES_RE = re.compile(r'^([ \t]*)if\s+"images"\s+in\s+node_output\s*:', re.M)
HANDLER_RE = re.compile(r"^(def handler\([^)]*\):\r?\n)", re.M)
DETAILS_RE = re.compile(r'"details"\s*:\s*errors')
CANDIDATES = (
    Path("/handler.py"),
    Path("/comfyui/handler.py"),
    Path("/rp_handler.py"),
    Path("/workspace/handler.py"),
    Path("/src/handler.py"),
    Path("/src/rp_handler.py"),
)

DIAG_MARK = "_fig_diag_wan"


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

def _fig_diag_wan(job):
    """只定位：把 WanVideoModelLoader 入参的值和类型打成一行，失败时进 details。"""
    try:
        inp = (job or {}).get("input") or {}
        wf = inp.get("workflow") or inp.get("prompt") or {}
        parts = ["FIG_DIAG=v14"]
        if not isinstance(wf, dict):
            text = "FIG_DIAG=v14 workflow_type=" + type(wf).__name__
            print(text, flush=True)
            return text
        found = 0
        for nid, node in wf.items():
            if not isinstance(node, dict):
                continue
            if node.get("class_type") != "WanVideoModelLoader":
                continue
            found += 1
            inputs = node.get("inputs") if isinstance(node.get("inputs"), dict) else {}
            for key in ("attention_mode", "quantization", "model", "base_precision", "load_device"):
                val = inputs.get(key)
                parts.append("%s %s=%r type=%s" % (nid, key, val, type(val).__name__))
        if found == 0:
            keys = ",".join(list(wf)[:24])
            parts.append("no WanVideoModelLoader keys=" + keys)
        text = " | ".join(parts)
        print(text, flush=True)
        return text
    except Exception as exc:
        text = "FIG_DIAG=v14 err=%s" % exc
        print(text, flush=True)
        return text

def _fig_with_diag(errors):
    """失败 details 末尾补上诊断行。"""
    out = list(errors) if errors else []
    diag = getattr(_fig_diag_wan, "_last", "")
    if diag and diag not in out:
        out.append(diag)
    return out

_fig_link_volume_models()
print("FIG_DIAG=v14 ready", flush=True)
'''


def inject_volume_links(text: str) -> str:
    """Worker 启动时挂盘符号链接，并注入诊断函数。"""
    if DIAG_MARK in text:
        return text
    return LINK_SNIPPET + "\n" + text


def inject_handler_wrap(text: str) -> str:
    """在 handler(job) 入口记下节点 22 入参。"""
    if re.search(r"^def handler\\([^)]*\\):\\r?\\n[ \\t]*_fig_diag_wan\\._last", text, re.M):
        return text
    match = HANDLER_RE.search(text)
    if not match:
        print("WARN: def handler not found")
        return text
    inject = "    _fig_diag_wan._last = _fig_diag_wan(job)\\n"
    return text[: match.end()] + inject + text[match.end() :]


def inject_details(text: str) -> str:
    """失败返回的 details 带上诊断行。"""
    if "_fig_with_diag(errors)" in text:
        return text
    return DETAILS_RE.sub('"details": _fig_with_diag(errors)', text)


def patch_text(text: str) -> str | None:
    """把 gifs 列表并进 images；对不上官方写法时返回 None。"""
    if 'if "gifs" in node_output' in text:
        return text
    match = IMAGES_RE.search(text)
    if not match:
        return None
    indent = match.group(1)
    insert = (
        f'{indent}if "gifs" in node_output:\\n'
        f'{indent}    node_output.setdefault("images", [])\\n'
        f'{indent}    node_output["images"].extend(node_output["gifs"])\\n'
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
        new_text = inject_details(new_text)
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
