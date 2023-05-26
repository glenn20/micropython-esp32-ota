# esp32_ota module for MicroPython on ESP32
# MIT license; Copyright (c) 2023 Glenn Moloney @glenn20

# Based on OTA class by Thorsten von Eicken (@tve):
#   https://github.com/tve/mqboard/blob/master/mqrepl/mqrepl.py


from esp32 import Partition
from flashbdev import bdev

from . import current_ota, next_ota


def partition_table() -> list[str]:
    partitions = [p.info() for p in Partition.find(Partition.TYPE_APP)]
    partitions.extend([p.info() for p in Partition.find(Partition.TYPE_DATA)])
    partitions.sort(key=lambda i: i[2])  # Sort by address
    ptype = {Partition.TYPE_APP: "app", Partition.TYPE_DATA: "data"}
    subtype = [
        {0: "factory", 16: "ota_0", 17: "ota_1", 18: "ota_2"},  # APP subtypes
        {0: "ota", 1: "phy", 2: "nvs", 129: "fat"},  # DATA subtypes
    ]
    table = [
        "Partition table:",
        "# Name       Type     SubType      Offset       Size (bytes)",
    ]
    table.extend(
        [
            f"  {p[4]:10s} {ptype[p[0]]:8s} {subtype[p[0]][p[1]]:8} {p[2]:#10x} {p[3]:#10x} {p[3]:10,}"
            for p in partitions
        ]
    )
    return table


def status() -> None:
    print(f"Micropython firmware is loading from partition '{current_ota.info()[4]}'.")
    if next_ota:
        print(f"The next OTA partition is '{next_ota.info()[4]}'.")
    else:
        print(f"The bootloader does not support OTA.")
    print(f"The / filesystem is mounted from partition '{bdev.info()[4]}'.")
    print("\n".join(partition_table()))
