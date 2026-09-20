"""卸掉会炸的官方 sageattention，写入 SDPA 同名接口，并强制 loadmodel 使用 sdpa。"""
from __future__ import annotations

import py_compile
import sysconfig
from pathlib import Path

FIG_MARK = "FIG_WAN_FORCE_SDPA"

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


def _loader_files() -> list[Path]:
    """找出所有 nodes_model_loading.py。"""
    base = Path("/comfyui/custom_nodes")
    found: list[Path] = []
    if base.is_dir():
        print("custom_nodes", [path.name for path in sorted(base.iterdir())])
        found.extend(base.glob("*/nodes_model_loading.py"))
    print("loaders", [str(path) for path in found])
    return found


def inject_force_sdpa(text: str) -> str:
    """在 sage 判断前插入强制 sdpa，避免 `"sage" in 3`。"""
    if FIG_MARK in text:
        return text
    needles = (
        'if "sage" in attention_mode:',
        'if isinstance(attention_mode, str) and "sage" in attention_mode:',
    )
    idx = -1
    for needle in needles:
        idx = text.find(needle)
        if idx != -1:
            break
    if idx == -1:
        raise SystemExit("sage check not found")
    line_start = text.rfind("\n", 0, idx) + 1
    indent = text[line_start:idx]
    force = (
        f"{indent}attention_mode = \"sdpa\"  # {FIG_MARK}\n"
        f"{indent}quantization = quantization if isinstance(quantization, str) else \"disabled\"\n"
        f"{indent}model = model if isinstance(model, str) else str(model)\n"
    )
    return text[:line_start] + force + text[line_start:]


def patch_wan_loader() -> None:
    """强制 sdpa，并加固其余 `in` 判断。"""
    loaders = _loader_files()
    if not loaders:
        raise SystemExit("nodes_model_loading.py not found")
    for loader in loaders:
        text = inject_force_sdpa(loader.read_text(encoding="utf-8"))
        for needle, repl in IN_REPLACEMENTS:
            text = text.replace(needle, repl)
        loader.write_text(text, encoding="utf-8")
        py_compile.compile(str(loader), doraise=True)
        snippet = loader.read_text(encoding="utf-8")
        if FIG_MARK not in snippet:
            raise SystemExit(f"force mark missing: {loader}")
        pos = snippet.find(FIG_MARK)
        print("patched", loader)
        print(snippet[max(0, pos - 80) : pos + 160])
    print(FIG_MARK, "ok")


def main() -> None:
    """安装 shim 并修补 WanVideoWrapper。"""
    write_shim()
    patch_wan_loader()


if __name__ == "__main__":
    main()
