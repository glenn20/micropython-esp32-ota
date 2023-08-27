# esp32_ota module for MicroPython on ESP32
# MIT license; Copyright (c) 2023 Glenn Moloney @glenn20

# Based on OTA class by Thorsten von Eicken (@tve):
#   https://github.com/tve/mqboard/blob/master/mqrepl/mqrepl.py


import sys
import time

import machine
from esp32 import Partition
from flashbdev import bdev
from micropython import const

OTA_UNSUPPORTED = const(-261)
ESP_ERR_OTA_VALIDATE_FAILED = const(-5379)
OTA_MIN: int = const(16)  # type: ignore
OTA_MAX: int = const(32)  # type: ignore


current_ota = Partition(Partition.RUNNING)  # Partition we booted from
boot_ota = Partition(Partition.BOOT)  # Partition we will boot from on next boot
next_ota = None  # Partition for the next OTA update (if device is OTA enabled)
try:
    next_ota = current_ota.get_next_update()
except OSError:
    pass


# Return True if the device is configured for OTA updates
def ready() -> bool:
    return next_ota is not None


def partition_table() -> list[tuple[int, int, int, int, str, bool]]:
    partitions = [p.info() for p in Partition.find(Partition.TYPE_APP)]
    partitions.extend([p.info() for p in Partition.find(Partition.TYPE_DATA)])
    partitions.sort(key=lambda i: i[2])  # Sort by address
    return partitions


def partition_table_print() -> None:
    ptype = {Partition.TYPE_APP: "app", Partition.TYPE_DATA: "data"}
    subtype = [
        {0: "factory"} | {i: f"ota_{i-OTA_MIN}" for i in range(OTA_MIN, OTA_MAX)},
        {0: "ota", 1: "phy", 2: "nvs", 129: "fat"},  # DATA subtypes
    ]
    print("Partition table:")
    print("# Name       Type     SubType      Offset       Size (bytes)")
    for p in partition_table():
        print(
            f"  {p[4]:10s} {ptype[p[0]]:8s} {subtype[p[0]][p[1]]:8} "
            + f"{p[2]:#10x} {p[3]:#10x} {p[3]:10,}"
        )


# Return a list of OTA partitions sorted by partition subtype number
def ota_partitions() -> list[Partition]:
    partitions: list[Partition] = [
        p
        for p in Partition.find(Partition.TYPE_APP)
        if OTA_MIN <= p.info()[1] < OTA_MAX
    ]
    # Sort by the OTA partition subtype: ota_0 (16), ota_1 (17), ota_2 (18), ...
    partitions.sort(key=lambda p: p.info()[1])
    return partitions


# Print a detailed summary of the OTA status of the device
def status() -> None:
    upyversion, pname = sys.version.split(" ")[2], current_ota.info()[4]
    print(f"Micropython {upyversion} has booted from partition '{pname}'.")
    if boot_ota.info() != current_ota.info():
        print(f" - will boot from partition '{boot_ota.info()[4]}' on next reboot.")
    if not ota_partitions():
        print("There are no OTA partitions available.")
    elif not next_ota:
        print("No spare OTA partition is available for update.")
    else:
        print(f"The next OTA partition for update is '{next_ota.info()[4]}'.")
    print(f"The / filesystem is mounted from partition '{bdev.info()[4]}'.")
    partition_table_print()


# Reboot the device after the provided delay
def ota_reboot(delay=10) -> None:
    for i in range(delay, 0, -1):
        print(f"\rRebooting in {i:2} seconds (ctrl-C to cancel)", end="")
        time.sleep(1)
    print()
    machine.reset()  # Reboot into the new image


# Micropython does not support forcing an OTA rollback so we do it by hand:
# - find the previous ota partition, validate the image and set it bootable.
# Raises OSError(-5379) if validation of the boot image fails.
# Raises OSError(-261) if no OTA partitions are available.
def force_rollback(reboot=False) -> None:
    partitions = ota_partitions()
    for i, p in enumerate(partitions):
        if p.info() == current_ota.info():  # Compare by partition offset
            partitions[i - 1].set_boot()  # Set the previous partition to be bootable
            if reboot:
                ota_reboot()
            return
    raise OSError(OTA_UNSUPPORTED)
