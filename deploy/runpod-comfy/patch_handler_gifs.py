"""把 worker-comfyui handler 里 VHS 的 gifs 输出并进 images，否则数字人 mp4 会被丢掉。"""
from pathlib import Path

NEEDLE = '            if "images" in node_output:'
INSERT = '''            if "gifs" in node_output:
                node_output.setdefault("images", [])
                node_output["images"].extend(node_output["gifs"])
            if "images" in node_output:'''

CANDIDATES = (
    Path("/handler.py"),
    Path("/comfyui/handler.py"),
    Path("/rp_handler.py"),
    Path("/workspace/handler.py"),
)


def main() -> None:
    targets = [p for p in CANDIDATES if p.is_file()]
    if not targets:
        targets = list(Path("/").glob("**/handler.py"))
    patched = 0
    for path in targets:
        text = path.read_text(encoding="utf-8")
        if "gifs" in node_output:" in text:
            print(f"already patched {path}")
            patched += 1
            continue
        if NEEDLE not in text:
            print(f"skip {path}: pattern not found")
            continue
        path.write_text(text.replace(NEEDLE, INSERT, 1), encoding="utf-8")
        print(f"patched {path}")
        patched += 1
    if patched == 0:
        raise SystemExit("handler.py not patched")


if __name__ == "__main__":
    main()
