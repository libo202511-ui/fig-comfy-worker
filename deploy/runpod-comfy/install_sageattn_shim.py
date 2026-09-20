"""卸掉会炸的官方 sageattention，写入 SDPA 同名接口，并修正 attention_mode 为 int 时的崩溃。"""
from __future__ import annotations

import sysconfig
from pathlib import Path

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

# 官方写法：if "sage" in attention_mode，attention_mode 若是 combo 下标(int)会炸
WAN_NEEDLE = 'if "sage" in attention_mode:'
WAN_REPL = (
    "if not isinstance(attention_mode, str):\n"
    "            try:\n"
    "                attention_mode = attention_modes[int(attention_mode)]\n"
    "            except Exception:\n"
    "                attention_mode = str(attention_mode)\n"
    '        if isinstance(attention_mode, str) and "sage" in attention_mode:'
)


def write_shim() -> None:
    """把 SDPA 兼容层写进 site-packages/sageattention。"""
    pkg = Path(sysconfig.get_path("purelib")) / "sageattention"
    pkg.mkdir(parents=True, exist_ok=True)
    (pkg / "__init__.py").write_text(SHIM, encoding="utf-8")
    print("sageattn shim written", pkg)


def patch_wan_loader() -> None:
    """把 WanVideoModelLoader 的 sage 判断改成能吃 int / str。"""
    roots = (
        Path("/comfyui/custom_nodes/ComfyUI-WanVideoWrapper"),
        Path("/comfyui/custom_nodes/comfyui-wanvideowrapper"),
    )
    patched = 0
    for root in roots:
        path = root / "nodes_model_loading.py"
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8")
        if WAN_REPL in text:
            print("already patched", path)
            patched += 1
            continue
        if WAN_NEEDLE not in text:
            print("needle missing", path)
            continue
        path.write_text(text.replace(WAN_NEEDLE, WAN_REPL, 1), encoding="utf-8")
        print("patched", path)
        patched += 1
    if patched == 0:
        raise SystemExit("WanVideoModelLoader not patched")


def main() -> None:
    """安装 shim 并修补 WanVideoWrapper。"""
    write_shim()
    patch_wan_loader()


if __name__ == "__main__":
    main()
