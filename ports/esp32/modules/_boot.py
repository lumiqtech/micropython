import gc
import vfs
from flashbdev import bdev

try:
    if bdev:
        vfs.mount(bdev, "/")
    print("Boot hello!")
except OSError:
    import inisetup

    inisetup.setup()

gc.collect()
