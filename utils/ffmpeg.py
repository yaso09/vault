import sys

is_android = hasattr(sys, "getandroidapilevel")

if is_android:
    sys.path.insert(0, "libs")

from wasmtime import Engine, Store, Module, Linker, WasiConfig
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent
BINARIES_DIR = BASE_DIR / "binaries"

ffmpegPath = BINARIES_DIR / "ffmpeg.wasm"
ffprobePath = BINARIES_DIR / "ffprobe.wasm"


def ffmpeg(args: list[str], workspace_dir: str = str(Path.cwd())):
    workspace_path = Path(workspace_dir).resolve()

    engine = Engine()
    store = Store(engine)

    wasi_config = WasiConfig()
    wasi_config.argv = ["ffmpeg.wasm"] + args
    wasi_config.inherit_stdout()
    wasi_config.inherit_stderr()
    wasi_config.preopen_dir(str(workspace_path), "/")

    store.set_wasi(wasi_config)

    linker = Linker(engine)
    linker.define_wasi()

    module = Module.from_file(engine, str(ffmpegPath))
    instance = linker.instantiate(store, module)

    start = instance.exports(store)["_start"]

    try:
        start(store)
        return 0

    except RuntimeError as e:
        msg = str(e).lower()

        # WASI exit detection (robust)
        if "exit" in msg:
            # exit code genelde mesajda olur
            import re
            m = re.search(r"exit status (\d+)", msg)
            if m:
                return int(m.group(1))
            return 0

        # gerçek crash
        return -1
