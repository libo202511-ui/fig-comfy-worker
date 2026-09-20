"""卸掉会炸的官方 sageattention，写入 SDPA 同名接口，并关掉 sage 的 in 判断。"""
from __future__ import annotations

import py_compile
import sysconfig
from pathlib import Path

FIG_MARK = "FIG_WAN_V12"

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

SAGE_REPLACEMENTS = (
    ('if "sage" in attention_mode:', f"if False and attention_mode:  # {FIG_MARK}"),
    ('if isinstance(attention_mode, str) and "sage" in attention_mode:', f"if False and attention_mode:  # {FIG_MARK}"),
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


def patch_wan_loader() -> None:
    """关掉 sage 分支，避免 '"sage" in 3'。"""
    roots = _wan_roots()
    if not roots:
        raise SystemExit("WanVideoWrapper not found")
    marked = False
    for root in roots:
        for path in root.rglob("*.py"):
            text = path.read_text(encoding="utf-8")
            original = text
            for needle, repl in SAGE_REPLACEMENTS:
                text = text.replace(needle, repl)
            if text == original:
                continue
            path.write_text(text, encoding="utf-8")
            py_compile.compile(str(path), doraise=True)
            print("patched", path)
            if FIG_MARK in text:
                marked = True
    if not marked:
        raise SystemExit(f"{FIG_MARK} mark missing")
    print(FIG_MARK, "ok")


def main() -> None:
    """安装 shim 并修补 WanVideoWrapper。"""
    write_shim()
    patch_wan_loader()


if __name__ == "__main__":
    main()
