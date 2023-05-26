# esp32_ota module for MicroPython on ESP32
# MIT license; Copyright (c) 2023 Glenn Moloney @glenn20

# Based on OTA class by Thorsten von Eicken (@tve):
#   https://github.com/tve/mqboard/blob/master/mqrepl/mqrepl.py


from esp32 import Partition

current_ota = Partition(Partition.RUNNING)
next_ota = None
try:
    next_ota = current_ota.get_next_update()
except OSError:
    pass


# Mark this boot as successful: prevent rollback to last image on next reboot.
def stop_rollback() -> None:
    # Raise OSError(-261) if bootloader is not OTA capable
    Partition.mark_app_valid_cancel_rollback()


# Return True if the device is configured for OTA updates
def ready() -> bool:
    return next_ota is not None


def OTA():
    from . import writer

    return writer.OTA()
