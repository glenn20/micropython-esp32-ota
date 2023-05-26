# esp32_ota module for MicroPython on ESP32
# MIT license; Copyright (c) 2023 Glenn Moloney @glenn20

# Based on OTA class by Thorsten von Eicken (@tve):
#   https://github.com/tve/mqboard/blob/master/mqrepl/mqrepl.py


import time

from esp32 import Partition

from .blockdev_writer import BlockDevWriter


# Mark this boot as successful: prevent rollback to last image on next reboot.
def stop_rollback() -> None:
    # Raise OSError(-261) if bootloader is not OTA capable
    Partition.mark_app_valid_cancel_rollback()


# OTA manages a MicroPython firmware update over-the-air. It assumes that there
# are two "app" partitions in the partition table and updates the one that is
# not currently running. When the update is complete, it sets the new partition
# as the next one to boot. It does not reset/restart, use machine.reset()
# explicitly. Remember to call ota.stop_rollback() after a successful reboot to
# the new image.
class OTA:
    def __init__(
        self,
        sha: str | bytes = "",
        length: int = 0,
        verify: bool = True,
        verbose: bool = True,
        reboot: bool = False,
    ):
        self._reboot = reboot
        # Get the next free OTA partition
        # Raise OSError(ENOENT) if no OTA partition available
        self.part: Partition = Partition(Partition.RUNNING).get_next_update()
        # Raise OSError(-261) if bootloader is not OTA capable
        name: str = self.part.info()[4]
        stop_rollback()
        if verbose:
            print(f"Writing new micropython image to OTA partition '{name}'...")
        self.writer = BlockDevWriter(self.part, sha, length, verify, verbose)

    def write(self, data: bytearray) -> int:
        return self.writer.write(data)

    def write_file(self, f) -> int:
        return self.writer.write_file(f)

    def close(self) -> bool:
        ret = self.writer.close()
        # Set as boot partition for next reboot
        self.part.set_boot()  # Raise OSError(-5379) if partition is not valid
        print(f"OTA Partition '{self.part.info()[4]}' updated successfully.")
        print(f"Micropython will be loaded from '{self.part.info()[4]}' on next boot.")
        print(
            "Remember to call "
            "esp32.Partition.mark_app_valid_cancel_rollback() after reboot."
        )
        if self._reboot:
            for i in range(10, 0, -1):
                print(f"\rRebooting in {i:2} seconds (ctrl-C to cancel)", end="")
                time.sleep(1)
            print()
            import machine

            machine.reset()  # Reboot into the new image
        return ret

    def __enter__(self):
        return self

    def __exit__(self, e_t, e_v, e_tr):
        if e_t is None:
            self.close()
