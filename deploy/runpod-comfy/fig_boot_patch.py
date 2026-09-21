"""Comfy 启动前改磁盘上所有 Wan 的 nodes_model_loading.py（含 Network Volume）。

创建人：LYC
创建时间：2026-09-21
必须在 Comfy import 之前跑，否则改文件也进不了正在执行的 loadmodel。
"""
from __future__ import annotations

from pathlib import Path

FIG = "FIG_BOOT=v15"

SAGE_REPLACEMENTS = (
    ('if "sage" in attention_mode:', f"if False:  # {FIG}"),
    ('if isinstance(attention_mode, str) and "sage" in attention_mode:', f"if False:  # {FIG}"),
    ("if False and attention_mode:", f"if False:  # {FIG}"),
)

IN_REPLACEMENTS = (
    ('if "fp8" in quantization:', 'if "fp8" in str(quantization):'),
    ('if "fast" in quantization:', 'if "fast" in str(quantization):'),
    ('if "scaled" in quantization:', 'if "scaled" in str(quantization):'),
    ('if "e4" in quantization:', 'if "e4" in str(quantization):'),
    ('elif "scaled" in quantization', 'elif "scaled" in str(quantization)'),
    ('"fast" in quantization', '"fast" in str(quantization)'),
)

ROOTS = (
    Path("/comfyui/custom_nodes"),
    Path("/runpod-volume"),
    Path("/workspace"),
)


def _loaders() -> list[Path]:
    """找出可能被 Comfy import 的 nodes_model_loading.py。"""
    found: list[Path] = []
    for root in ROOTS:
        if not root.is_dir():
            continue
        try:
            for path in root.rglob("nodes_model_loading.py"):
                name = str(path).lower()
                if "wan" in name or "wanvideo" in name:
                    found.append(path)
        except OSError as exc:
            print("FIG_BOOT skip root", root, exc, flush=True)
    return found


def _inject_coerce(text: str) -> str:
    """在 WanVideoModelLoader.loadmodel 第一行收成字符串。"""
    if f"attention_mode = \"sdpa\"  # {FIG}" in text:
        return text
    cls_idx = text.find("class WanVideoModelLoader")
    if cls_idx < 0:
        return text
    load_idx = text.find("def loadmodel(", cls_idx)
    if load_idx < 0:
        return text
    sig_end = text.find("):\n", load_idx)
    if sig_end < 0:
        sig_end = text.find("):\r\n", load_idx)
    if sig_end < 0:
        return text
    insert_at = text.find("\n", sig_end) + 1
    coerce = (
        f'        attention_mode = attention_mode if isinstance(attention_mode, str) else "sdpa"  # {FIG}\n'
        '        quantization = quantization if isinstance(quantization, str) else "disabled"\n'
        "        model = model if isinstance(model, str) else str(model)\n"
    )
    return text[:insert_at] + coerce + text[insert_at:]


def patch_file(path: Path) -> bool:
    """改一个文件，有变化返回 True。"""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        print("FIG_BOOT read skip", path, exc, flush=True)
        return False
    if "WanVideoModelLoader" not in text and "attention_mode" not in text:
        return False
    original = text
    text = _inject_coerce(text)
    for needle, repl in SAGE_REPLACEMENTS:
        text = text.replace(needle, repl)
    for needle, repl in IN_REPLACEMENTS:
        text = text.replace(needle, repl)
    if text == original:
        print("FIG_BOOT unchanged", path, flush=True)
        return False
    try:
        path.write_text(text, encoding="utf-8")
    except OSError as exc:
        print("FIG_BOOT write skip", path, exc, flush=True)
        return False
    print("FIG_BOOT patched", path, flush=True)
    return True


def main() -> None:
    """启动时扫描并改写。"""
    loaders = _loaders()
    print("FIG_BOOT candidates", [str(p) for p in loaders], flush=True)
    if not loaders:
        print("FIG_BOOT none", flush=True)
        return
    changed = 0
    for path in loaders:
        if patch_file(path):
            changed += 1
    print("FIG_BOOT done", changed, flush=True)


if __name__ == "__main__":
    main()
