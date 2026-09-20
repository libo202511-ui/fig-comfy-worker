"""卸掉会炸的官方 sageattention，写入 SDPA 同名接口，并修正 attention_mode 为 int 时的崩溃。"""
from __future__ import annotations

import py_compile
import sysconfig
from pathlib import Path

FIG_MARK = "FIG_WAN_PATCH_V3"

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

# 插在 loadmodel 的 assert 后面：combo 下标(int)先还原成字符串，避免 "sage" in 3
COERCE_NEEDLE = (
    'assert not (vram_management_args is not None and block_swap_args is not None), '
    '"Can\'t use both block_swap_args and vram_management_args at the same time"'
)
COERCE_REPL = COERCE_NEEDLE + """
    # """ + FIG_MARK + """
    if not isinstance(attention_mode, str):
        try:
            attention_mode = attention_modes[int(attention_mode)]
        except Exception:
            attention_mode = "sdpa"
    if not isinstance(quantization, str):
        quantization = "disabled"
    if not isinstance(model, str):
        model = str(model)
"""

IN_REPLACEMENTS = (
    ('if "sage" in attention_mode:', 'if isinstance(attention_mode, str) and "sage" in attention_mode:'),
    ('if "flash" in attention_mode:', 'if isinstance(attention_mode, str) and "flash" in attention_mode:'),
    ('if "fp8" in quantization:', 'if isinstance(quantization, str) and "fp8" in quantization:'),
    ('if "fast" in quantization:', 'if isinstance(quantization, str) and "fast" in quantization:'),
    ('if "scaled" in quantization:', 'if isinstance(quantization, str) and "scaled" in quantization:'),
    ('if "e4" in quantization:', 'if isinstance(quantization, str) and "e4" in quantization:'),
    ('if "480" in model or "fun" in model.lower()', 'if isinstance(model, str) and ("480" in model or "fun" in model.lower())'),
    ('elif "720" in model:', 'elif isinstance(model, str) and "720" in model:'),
)


def write_shim() -> None:
    """把 SDPA 兼容层写进 site-packages/sageattention。"""
    pkg = Path(sysconfig.get_path("purelib")) / "sageattention"
    pkg.mkdir(parents=True, exist_ok=True)
    (pkg / "__init__.py").write_text(SHIM, encoding="utf-8")
    print("sageattn shim written", pkg)


def _wrapper_roots() -> list[Path]:
    """WanVideoWrapper 可能的安装目录。"""
    return [
        Path("/comfyui/custom_nodes/ComfyUI-WanVideoWrapper"),
        Path("/comfyui/custom_nodes/comfyui-wanvideowrapper"),
    ]


def _patch_text(text: str) -> str:
    """对单文件做 coerce + `in` 判断加固。"""
    if FIG_MARK in text:
        return text
    if COERCE_NEEDLE in text:
        text = text.replace(COERCE_NEEDLE, COERCE_REPL, 1)
    for needle, repl in IN_REPLACEMENTS:
        text = text.replace(needle, repl)
    return text


def patch_wan_loader() -> None:
    """把 WanVideoWrapper 里所有 `"x" in attention_mode/quantization` 改成先判类型。"""
    patched = 0
    for root in _wrapper_roots():
        if not root.is_dir():
            continue
        for path in root.rglob("*.py"):
            try:
                text = path.read_text(encoding="utf-8")
            except OSError:
                continue
            new_text = _patch_text(text)
            if new_text == text:
                continue
            path.write_text(new_text, encoding="utf-8")
            py_compile.compile(str(path), doraise=True)
            print("patched", path)
            patched += 1
        loader = root / "nodes_model_loading.py"
        if loader.is_file() and FIG_MARK not in loader.read_text(encoding="utf-8"):
            raise SystemExit(f"FIG mark missing after patch: {loader}")
        if loader.is_file():
            patched += 1
    if patched == 0:
        raise SystemExit("WanVideoModelLoader not patched")
    print(FIG_MARK, "ok")


def main() -> None:
    """安装 shim 并修补 WanVideoWrapper。"""
    write_shim()
    patch_wan_loader()


if __name__ == "__main__":
    main()
