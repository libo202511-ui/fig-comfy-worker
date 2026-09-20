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

# 只替换这一句（官方一定有）。前导空格留在原行上，后面各行按 8 空格对齐 loadmodel
SAGE_NEEDLE = 'if "sage" in attention_mode:'
SAGE_REPL = (
    f"# {FIG_MARK}\n"
    "        if not isinstance(attention_mode, str):\n"
    "            try:\n"
    "                attention_mode = attention_modes[int(attention_mode)]\n"
    "            except Exception:\n"
    "                attention_mode = \"sdpa\"\n"
    "        if not isinstance(quantization, str):\n"
    "            quantization = \"disabled\"\n"
    "        if not isinstance(model, str):\n"
    "            model = str(model)\n"
    "        if isinstance(attention_mode, str) and \"sage\" in attention_mode:"
)

IN_REPLACEMENTS = (
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
    """按 nodes_model_loading.py 定位 WanVideoWrapper，不写死大小写。"""
    base = Path("/comfyui/custom_nodes")
    found: list[Path] = []
    if base.is_dir():
        print("custom_nodes", [p.name for p in sorted(base.iterdir())])
        for path in base.iterdir():
            if path.is_dir() and (path / "nodes_model_loading.py").is_file():
                found.append(path)
    print("wrapper roots", [str(path) for path in found])
    return found


def _patch_other(text: str) -> str:
    """加固其余 `\"x\" in int` 判断，不动已经打过的 sage 段。"""
    for needle, repl in IN_REPLACEMENTS:
        text = text.replace(needle, repl)
    return text


def patch_wan_loader() -> None:
    """在 loadmodel 的 sage 判断前插入 int→str，并给文件打上 FIG 标记。"""
    roots = _wrapper_roots()
    if not roots:
        raise SystemExit("WanVideoWrapper nodes_model_loading.py not found")
    marked = 0
    for root in roots:
        loader = root / "nodes_model_loading.py"
        text = loader.read_text(encoding="utf-8")
        print("loader", loader, "sage_needle", SAGE_NEEDLE in text, "mark", FIG_MARK in text)
        if FIG_MARK not in text:
            if SAGE_NEEDLE not in text:
                raise SystemExit(f"sage needle missing: {loader}")
            text = text.replace(SAGE_NEEDLE, SAGE_REPL, 1)
        text = _patch_other(text)
        loader.write_text(text, encoding="utf-8")
        py_compile.compile(str(loader), doraise=True)
        if FIG_MARK not in loader.read_text(encoding="utf-8"):
            raise SystemExit(f"FIG mark missing after patch: {loader}")
        print("patched loader", loader)
        marked += 1
        for path in root.rglob("*.py"):
            if path == loader:
                continue
            try:
                other = path.read_text(encoding="utf-8")
            except OSError:
                continue
            new_other = _patch_other(other)
            if new_other == other:
                continue
            path.write_text(new_other, encoding="utf-8")
            py_compile.compile(str(path), doraise=True)
            print("patched", path)
    if marked == 0:
        raise SystemExit("WanVideoModelLoader not patched")
    print(FIG_MARK, "ok")


def main() -> None:
    """安装 shim 并修补 WanVideoWrapper。"""
    write_shim()
    patch_wan_loader()


if __name__ == "__main__":
    main()
