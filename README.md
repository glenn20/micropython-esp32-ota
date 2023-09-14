# Micropython OTA tools for ESP32 devices

Some classes and tools for Over-The-Air (OTA) firmware updates on ESP32. I
wanted a simple and flexible interface for managing and running OTA updates for
ESP32* devices. These tools are for managing OTA updates of the micropython
firmware installed in the device flash storage (not the python files in the
mounted filesystem).

Contents: [Usage](#usage) | [Installation](#installation) | [How it
   Works:](#how-it-works) | Module API docs: [ota.update](#otaupdate-module),
   [ota.rollback](#otarollback-module), [ota.status](#otastatus-module)

## Usage

Write a new micropython image from a web server to the next OTA partition on the
flash storage:

```py
>>> from ota.update import OTA
>>> with OTA(verify=True, verbose=True, reboot=True) as ota:
>>>     ota.from_firmware_file("http://nas.local/micropython.bin")
Writing new micropython image to OTA partition 'ota_0'...
Device capacity: 384 x 4096 byte blocks.
Opening firmware file http://nas.local/micropython.bin...
Writing 380 blocks + 2032 bytes.
BLOCK 380 + 2032 bytes
Verifying SHA of the written data...Passed.
SHA256=7920d527d578e90ce074b23f9050ffe4ebbd8809b79da0b81493f6ba721d110e
OTA Partition 'ota_0' updated successfully.
Micropython will boot from 'ota_0' partition on next boot.
Remember to call ota.rollback.cancel() after successful reboot.
Rebooting in 10 seconds (ctrl-C to cancel)
```

Print the current status of the OTA partitions on the device:

```py
>>> import ota.status
>>> ota.status.status()
Micropython firmware v1.20.0 has booted from partition 'ota_0'.
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

After booting up successfully, stop the esp32 from [rolling
back](#otarollback-module) to the previous firmware on next boot (should do this
on every successful boot and app startup):

```py
import ota.rollback
ota.rollback.cancel()
```

## Installation

Install `ota` package with [`mpremote`](
  https://docs.micropython.org/en/latest/reference/packages.html#installing-packages-with-mpremote)
  into `/lib/ota/` on the device (as **.py** modules):

```bash
mpremote mip install github:glenn20/micropython-esp32-ota/mip/ota
```

or, install module as byte-compiled [**.mpy**](
  https://docs.micropython.org/en/latest/reference/mpyfiles.html) files

```bash
mpremote mip install github:glenn20/micropython-esp32-ota/mip/ota/mpy
```

Remember to ensure `/lib` is in your `sys.path`.

## How it works

### An OTA-enabled partition table

To support Over-The-Air updates, a micropython image requires a special
partition table, such as:

```text
Partition table:
# Name       Type     SubType      Offset       Size (bytes)
  nvs        data     nvs          0x9000     0x4000     16,384
  otadata    data     ota          0xd000     0x2000      8,192
  phy_init   data     phy          0xf000     0x1000      4,096
  ota_0      app      ota_0       0x10000   0x180000  1,572,864
  ota_1      app      ota_1      0x190000   0x180000  1,572,864
  vfs        data     fat        0x310000    0xf0000    983,040
```

- Use `ota.status.status()` to print the full partition table of your device.

For micropython, an OTA-enabled partition table usually includes:

- one partition with a subtype of **ota** (usually named **otadata**)
  - where the bootloader saves metadata about the state of the ota partitions
- two **app** partitions with subtypes of **ota_0** and **ota_1**.
  - The OTA updater writes new micropython firmware images into these partitions
- and usually one **data** partition named **vfs** or **fat**.

Any micropython image built with `BOARD_VARIANT=OTA` will have a partition table
like this (including the official OTA images at
<https://micropython.org/download/ESP32_GENERIC>).

### Writing new firmware into the `ota` partitions

The partition table has to make room for **two** **app** partitions on the
device (instead of the normal one). This means space is tight on a 4MB flash
device. The OTA partition usually has less room for each micropython firmware
image (1.5MB instead of 2MB) and much less room for the **vfs** filesystem
partition (<1MB instead of 2MB). Devices with more than 4MB of flash can use
larger **app** and **vfs** partitions.

Micropython will boot from one of the **ota_X** **app** partitions and write new
firmware to the other one. After writing new firmware to the other partition, it
will be set as the boot partition for the next reboot. The old firmware image is
still available in case it is necessary to **rollback** to the previous
firmware.

After booting from either **ota** partition, the micropython firmware will
automatically mount the `/` filesystem from the **vfs** partition.

### Micropython firmware for OTA updates

An OTA partition should be updated with a **"micropython app binary"**. The
micropython firmware ".bin" files downloaded from the [MicroPython downloads
page](https://micropython.org/download/) combine the bootloader, partition table
and the "micropython app binary", so can not be used for micropython OTA
updates.

There are three ways to obtain a `micropython.bin` you can use for OTA updates:

1. Download a `.app-bin` file from the [MicroPython downloads
   page](https://micropython.org/download/),
   - these are currently only available for the "Nightly builds".
1. Use the `micropython.bin` file in the `ports/esp32/build_XXX` folder
   - if you build your own micropython firmware, or
1. Extract the `micropython.bin` from a combined firmware binary (on linux):
   - `dd bs=4096 skip=15 if=firmware.bin of=micropython.bin`
     - for ESP32 and ESP32S2 images (skip first 61440 bytes of file)
   - `dd bs=4096 skip=16 if=firmware-S3.bin of=micropython.bin`
     - for ESP32S3 and ESP32C3 images (skip first 65536 bytes of file)

## API docs

### `ota.update` module

The `ota.update` module provides the `OTA` class which  can be used to write new
micropython firmware to the next **ota** partition on the device.

- class `ota.update.OTA(verify=True, verbose=True, reboot=False, sha="", length=0)`

  - Create an OTA class instance which can be used to write new micropython
    firmware on the device. May be used as a context manager in a **with**
    statement.
  - Checks that:
    - The bootloader is OTA-enabled (*CONFIG_BOOTLOADER_APP_ROLLBACK_ENABLE=y*)
    - There are OTA partitions available to write the new firmware
        ([`esp32.Partition.get_next_update()`](
        https://docs.micropython.org/en/latest/library/esp32.html#esp32.Partition))
  - Arguments:
    - `verify`: if true, read back the data from the partition on **close()** to
      verify the sha256sum matches the written data
    - `verbose`: if true, print out useful progress and diagnostic information
    - `reboot`: if true, reboot the device on **close()** - if all checks pass
    - `sha`: optionally provide the expected sha256sum of the firmware
    - `length`: optionally specify the length of the firmware file and check it
      will fit on device
      - **sha** and **length** may instead be provided as arguments to some
        methods below.

- Method: `OTA.from_firmware_file(url: str, sha="", length=0) -> int`

  - Read a micropython firmware from **url** and write it to the next **ota**
    partition. **sha** and **length** are used to validate the data written to
    the partition. Returns the number of bytes written to the partition.

    - `url` is a http[s] url or a filename on the device
    - `sha` (optional) is the expected sha256sum of the firmware file
    - `length` (optional) is the expected length of the firmware file (in bytes)

- Method: `OTA.from_json(url: str) -> int`

  - Read a JSON file from **url** (must end in ".json") containing the **url**,
    **sha** and **length** of the firmware file. Then, read the firmware file
    and write it to the next **ota** partition. Returns the number of bytes
    written to the partition.

    The JSON file should specify an object including the **firmware**, **sha**,
    and **length** keys, eg:

    ```json
    { "firmware": "micropython.bin",
      "sha": "7920d527d578e90ce074b23f9050ffe4ebbd8809b79da0b81493f6ba721d110e",
      "length": 1558512 }
    ```

    The **firmware** key provides a url (or filename) for the firmware image.
    This may be specified relative to the basename of the **url** for the json
    file.

- Method: `OTA.from_stream(f, sha="", length=0) -> int`

  - Read a micropython firmware from an open file/stream, `f`, and write it to
    the next **ota** partition. Returns the number of bytes written to the
    partition. **sha** and **length** are used to validate the data written to
    the partition.
  - `f` is an io stream (file-like object) which supports the **readinto()**
      method
  - `sha` (optional) is the expected sha256sum of the firmware file
  - `length` (optional) is the expected length of the firmware file (in bytes)

- Method: `OTA.write(data: bytes | bytearray) -> int`

  - Copy **data** to the end of the firmware file being written to the **ota**
    partition.

- Method: `OTA.close()`

  - Flush buffered data to the **ota** partition
    - Compute the sha256sum of data written
  - Check length of firmware matches expected length (if provided)
  - Check sha256sum of firmware matches expected hash (if provided)
  - If `verify` is true:
    - read back firmware from partition and check sha256sum matches
  - Validate the new firmware image and set the new OTA partition as boot
    partition ([esp32.Partition.set_boot()](
      https://docs.micropython.org/en/latest/library/esp32.html#esp32.Partition))
  - If `reboot` is true, perform a hard [reset](
    https://docs.micropython.org/en/latest/library/machine.html#machine.reset)
    of the device after a delay of 10 seconds.

  If all checks pass, the new firmware will be loaded after the next reboot. If
  any checks fail, a `ValueError` exception will be raised.

  - `OTA.close()` will be called automatically if `OTA` is used in a **with**
  statement (as a context manager).

#### Examples

```py
from ota.update import OTA

# Write firmware from a url provided in a JSON file
with OTA() as ota:
    ota.from_json("http://nas.local/micropython/micropython.json")

# Write firmware from a url or filename and reboot if successful and verified
with OTA(reboot=True) as ota:
    ota.from_firmware_file(
        "http://nas.local/micropython/micropython.bin",
        sha="7920d527d578e90ce074b23f9050ffe4ebbd8809b79da0b81493f6ba721d110e",
        length=1558512)

# Write firmware from an open stream:
with OTA() as ota:
    with open("/sdcard/micropython.bin", "rb") as f:
        ota.from_stream(f)

# Read a firmware file from a serial uart
remaining = 1558512
sha = "7920d527d578e90ce074b23f9050ffe4ebbd8809b79da0b81493f6ba721d110e"
with OTA(length=remaining, sha=sha) as ota:
    data = memoryview(bytearray(1024))
    gc.collect()
    while remaining > 0:
        n = uart.readinto(data[:min(remaining, len(data))]):
        ota.write(data[:n])
        remaining -= n

# Used without the "with" statement - must call close() explicitly
ota = OTA()
ota.from_json("http://nas.local/micropython/micropython.json")
ota.close()
```

### `ota.rollback` module

When booting a new OTA firmware for the first time, you need to tell the
bootloader if it is OK to continue using the new firmware. Otherwise, the
bootloader will assume something went wrong and automatically [**rollback**](
  https://docs.espressif.com/projects/esp-idf/en/latest/esp32/api-reference/system/ota.html#app-rollback)
to the previous firmware on the next reboot. You can use `ota.rollback.cancel()`
to tell the bootloader not to rollback to the previous firmware.

If the new firmware fails to startup or your app does not operate correctly with
the new firmware, reboot the device **without** cancelling the rollback and the
old firmware will be restored. You may also wish to use a [watchdog timer
(WDT)](https://docs.micropython.org/en/latest/library/machine.WDT.html) during
your app startup sequence to force a reboot if the startup hangs or fails before
you call `ota.rollback.cancel()`.

**Note:** the rollback mechanism is only available if the bootloader was
compiled with `CONFIG_BOOTLOADER_ROLLBACK_ENABLE=y`.

- function `ota.rollback.cancel()`

  - Tell the bootloader to continue booting this **ota** firmware partition by
    invoking [esp_ota_mark_app_valid_cancel_rollback()](
    https://docs.espressif.com/projects/esp-idf/en/latest/esp32/api-reference/system/ota.html#app-rollback).
  - A reasonable approach is to call `ota.rollback.cancel()` on every successful
    boot (eg. in `main.py` or after your app has successfully started up). The
    `ota.rollback` module is designed to be lightweight so you can call it every
    time your device boots up.

- function `ota.rollback.force()`

  - Manually set the next reboot to boot from the **other** *ota partition. This
    bypasses the bootloader's OTA rollback provisions, but lets you switch
    between the two firmwares on the device as you need.

- function `ota.rollback.cancel_force()`

  - Cancel any previous call to `ota.rollback.force()`. This function will
    manually set the boot partition for future boots to the currently booted
    partition.

## `ota.status` module

- function `ota.status.status()`

  - Check the current firmware is OTA-capable
  - Print the current partition table
  - Show which is the currently booted partition
  - Show the partition which will be used on next reboot

- function `ota.status.ready() -> bool`

  - Return `True` if the current device supports OTA firmware updates:
    - the bootloader was compiled with *CONFIG_BOOTLOADER_ROLLBACK_ENABLE=y*,
      and
    - the partition table supports OTA updates.
