# Micropython OTA tools for ESP32 devices

Some classes and tools for Over-The-Air (OTA) updates on ESP32.

These tools are for managing OTA updates of the micropython firmware installed
in the device flash storage (not the python files on the flash storage).

## `ota` module

Check the device is OTA-enabled:

```py
import ota
if not ota.ready():
    print("Install an OTA-enabled micropython firmware (or bootloader) to use OTA.")
```

After booting up successfully, stop the esp32 from rolling back to the previous
image:

```py
import ota
ota.stop_rollback()
```

Print the current status of the OTA partitions on the device:

```py
>>> from ota.status import status
>>> status()
Micropython firmware is loading from partition 'ota_0'.
The next OTA partition is 'ota_1'.
The / filesystem is mounted from partition 'vfs'.
Partition table:
# Name       Type     SubType      Offset       Size (bytes)
  nvs        data     nvs          0x9000     0x4000     16,384
  otadata    data     ota          0xd000     0x2000      8,192
  phy_init   data     phy          0xf000     0x1000      4,096
  ota_0      app      ota_0       0x10000   0x180000  1,572,864
  ota_1      app      ota_1      0x190000   0x180000  1,572,864
  vfs        data     fat        0x310000    0xf0000    983,040
>>>
```

### Writing a new micropython firmware with OTA

Write a new micropython image from a web server to the next OTA partition on the
flash storage:

```py
>>> import urequests
>>> from ota.writer import OTA
>>> with OTA() as ota:
>>>    r = urequests.get("http://nas.lan/micropython/micropython.bin")
>>>    ota.write_file(r.raw)
Writing new micropython image to OTA partition 'ota_1'...
Device: 384 x 4096 byte blocks.
Writing 372 blocks + 1824 bytes.
BLOCK 372 + 1824 bytes
Verifying 372 blocks + 1824 bytes...Passed.
SHA256=18026395faa6c39201b422017cdc4d136f8f84f654e4a79a7acf13ccac5dcb6f
OTA Partition 'ota_1' updated successfully.
Micropython will be loaded from 'ota_1' on next hard reboot.
Remember to call esp32.Partition.mark_app_valid_cancel_rollback() after reboot.
>>> r.close()
```

Write a new micropython firmware image from a file:

```py
import urequests
from ota.writer import OTA
with open("micropython.bin") as f, OTA() as ota:
    ota.write_file(f)
```

Set the expected length and sha256 hash of the micropython image file. The
length and hash will be checked and verified:

```py
import urequests
from ota.writer import OTA
file_name = "micropython.bin"
file_sha = "18026395faa6c39201b422017cdc4d136f8f84f654e4a79a7acf13ccac5dcb6f"
file_length = 1525536
f = open(file_name)
ota = OTA(sha=file_sha, length=file_length):
ota.write_file(f)
ota.close()
f.close()
```

## `ota.writer` module

The `ota.writer` modules provides the `OTA` class:

```py
OTA(sha="", length=0, verify=True, verbose=True, reboot=False)
```

which will:

- Check that:
  - The bootloader is OTA-enabled (CONFIG_BOOTLOADER_APP_ROLLBACK_ENABLE=y)
  - There are OTA partitions available to write the new firmware
    - `esp32.Partition(esp32.Partition.RUNNING).get_next_update()`
  - The image will fit in the OTA partition
- Write the new firmware image to the OTA partition
  - Compute sha256 hash of data written
- Check length of firmware matches expected length (if provided)
- Check sha256 of firmware matches expected hash (if provided)
- **If** `verify=True` is set:
  - Read back firmware from OTA partition and check sha256 hash matches
- **If all checks pass**:
  - Set the new OTA partition as boot partition (and verify the image):
    - `esp32.Partition.set_boot()`
  - **If** `reboot=True` is set, perform a hard reset of the device

If the `OTA` instance is successful and all checks are passed, the new firmware
will be loaded after the next reboot.

### Rollback

After booting into the new firmware, the ESP32 will automatically rollback to
the previous firmware on the next reboot, unless you mark the new firmware as
good by cancelling the rollback with
`esp32.Partition.mark_app_valid_cancel_rollback()` (or `ota.stop_rollback()`).

If the new firmware fails to startup or your app does not operate correctly,
reboot the device without cancelling the rollback.

A reasonable approach is to call `ota.stop_rollback()` on every boot (eg. in
`main.py` or after your app has successfully started up).

See the [ESP32
docs](https://docs.espressif.com/projects/esp-idf/en/latest/esp32/api-reference/system/ota.html#app-rollback)
for more information.
