"""卸掉会炸的官方 sageattention，写入 SDPA 同名接口，并在 loadmodel 入口强制字符串。"""
from __future__ import annotations

import py_compile
import re
import sysconfig
from pathlib import Path

FIG_MARK = "FIG_WAN_V11"

SHIM = '''import torch.nn.functional as F


def sageattn(q, k, v, attn_mask=None, dropout_p=0.0, is_causal=False, tensor_layout="HND", **kwargs):
    if tensor_layout == "NHD":
        q, k, v = q.transpose(1, 2), k.transpose(1, 2), v.transpose(1, 2)
    if not (q.dtype == k.dtype == v.dtype):
        k, v = k.to(q.dtype), v.to(q.dtype)
    out = F.scaled_dot_product_attention(
        q, k, v, attn_mask=attn_mask, dropout_p=dropout_p, is_causal=is_causal
    )
    if tensor_layout == "NHD":
        out = out.transpose(1, 2)
    return out


def sageattn_varlen(*args, **kwargs):
    raise NotImplementedError("sageattn_varlen")
'''

HELPER = (
    "def _fig_in(needle, haystack):\n"
    f'    """{FIG_MARK}: 避免 \'"x" in 3\'。"""\n'
    "    return isinstance(haystack, str) and needle in haystack\n"
    "\n"
)

COERCE = (
    f'        attention_mode = "sdpa"  # {FIG_MARK}\n'
    '        quantization = quantization if isinstance(quantization, str) else "disabled"\n'
    "        model = model if isinstance(model, str) else str(model)\n"
    '        base_precision = base_precision if isinstance(base_precision, str) else "fp16"\n'
    '        load_device = load_device if isinstance(load_device, str) else "offload_device"\n'
)

IN_PATTERNS = (
    (re.compile(r'(["\'])([^"\']+)\1\s+in\s+attention_mode\b'), r"_fig_in(\1\2\1, attention_mode)"),
    (re.compile(r'(["\'])([^"\']+)\1\s+in\s+quantization\b'), r"_fig_in(\1\2\1, quantization)"),
    (re.compile(r'(["\'])([^"\']+)\1\s+in\s+model\b(?![.\w])'), r"_fig_in(\1\2\1, model)"),
)


def write_shim() -> None:
    """把 SDPA 兼容层写进 site-packages/sageattention。"""
    pkg = Path(sysconfig.get_path("purelib")) / "sageattention"
    pkg.mkdir(parents=True, exist_ok=True)
    (pkg / "__init__.py").write_text(SHIM, encoding="utf-8")
    print("sageattn shim written", pkg)


def _wan_roots() -> list[Path]:
    """WanVideoWrapper 可能的目录名。"""
    base = Path("/comfyui/custom_nodes")
    roots: list[Path] = []
    if not base.is_dir():
        return roots
    print("custom_nodes", [path.name for path in sorted(base.iterdir())])
    for name in ("ComfyUI-WanVideoWrapper", "comfyui-wanvideowrapper"):
        root = base / name
        if root.is_dir():
            roots.append(root)
    return roots


def _ensure_helper(text: str) -> str:
    """文件头写入 _fig_in，避免重复。"""
    if "def _fig_in(" in text:
        return text
    return HELPER + text


def _rewrite_in_checks(text: str) -> str:
    """把 '"x" in attention_mode/quantization/model' 收成 _fig_in。"""
    for pattern, repl in IN_PATTERNS:
        text = pattern.sub(repl, text)
    return text


def _inject_loadmodel_coerce(text: str) -> str:
    """在 WanVideoModelLoader.loadmodel 第一行插入强制 sdpa。"""
    if FIG_MARK in text and "attention_mode = \"sdpa\"" in text:
        return text
    cls_idx = text.find("class WanVideoModelLoader")
    if cls_idx < 0:
        raise SystemExit("WanVideoModelLoader not found")
    load_idx = text.find("def loadmodel(", cls_idx)
    if load_idx < 0:
        raise SystemExit("loadmodel not found")
    sig_end = text.find("):\n", load_idx)
    if sig_end < 0:
        sig_end = text.find("):\r\n", load_idx)
    if sig_end < 0:
        raise SystemExit("loadmodel signature end not found")
    insert_at = text.find("\n", sig_end) + 1
    return text[:insert_at] + COERCE + text[insert_at:]


def patch_wan_loader() -> None:
    """入口强制字符串，并改掉所有危险的 in 判断。"""
    roots = _wan_roots()
    if not roots:
        raise SystemExit("WanVideoWrapper not found")
    patched_loader = False
    for root in roots:
        for path in root.rglob("*.py"):
            text = path.read_text(encoding="utf-8")
            original = text
            if path.name == "nodes_model_loading.py" and "class WanVideoModelLoader" in text:
                text = _inject_loadmodel_coerce(text)
                patched_loader = True
            if "in attention_mode" in text or "in quantization" in text or '" in model' in text:
                text = _rewrite_in_checks(text)
                text = _ensure_helper(text)
            if text == original:
                continue
            path.write_text(text, encoding="utf-8")
            py_compile.compile(str(path), doraise=True)
            print("patched", path)
    if not patched_loader:
        raise SystemExit("nodes_model_loading.py WanVideoModelLoader not patched")
    for root in roots:
        loader = root / "nodes_model_loading.py"
        if loader.is_file() and FIG_MARK in loader.read_text(encoding="utf-8"):
            print(FIG_MARK, "ok", loader)
            return
    raise SystemExit(f"{FIG_MARK} mark missing")


def main() -> None:
    """安装 shim 并修补 WanVideoWrapper。"""
    write_shim()
    patch_wan_loader()


if __name__ == "__main__":
    main()
