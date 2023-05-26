# partition_writer module for MicroPython on ESP32
# MIT license; Copyright (c) 2023 Glenn Moloney @glenn20

# Based on OTA class by Thorsten von Eicken (@tve):
#   https://github.com/tve/mqboard/blob/master/mqrepl/mqrepl.py

import binascii
import hashlib

from micropython import const

IOCTL_BLOCK_COUNT = const(4)
IOCTL_BLOCK_SIZE = const(5)
IOCTL_BLOCK_ERASE = const(6)


class Blockdev:
    def __init__(self, device, verbose: bool = True):
        self.device = device
        self.blocksize: int = device.ioctl(IOCTL_BLOCK_SIZE, None)
        self.blockcount: int = self.device.ioctl(IOCTL_BLOCK_COUNT, None)
        self.pos = 0
        self.end = 0
        self.verbose = verbose

    # The number of bytes written to the device
    def size(self) -> int:
        return self.end

    # Data must be a multiple of blocksize or less than blocksize
    # If len(data) < blocksize it must be the last write to the device.
    def write(self, data: bytearray | memoryview) -> int:
        block, remainder = divmod(self.pos, self.blocksize)
        if remainder:
            raise ValueError(f"Block {block} write not aligned at block boundary.")
        if len(data) % self.blocksize == 0:  # Write whole blocks
            self.device.writeblocks(block, data)
            if self.verbose:
                print(f"\rBLOCK {block}", end="")
        elif len(data) < self.blocksize:  # Write a partial block
            self.device.ioctl(IOCTL_BLOCK_ERASE, block)  # Erase block first
            self.device.writeblocks(block, data, 0)
            if self.verbose:
                print(f"\rBLOCK {block} + {len(data)} bytes", end="")
        else:
            raise ValueError(f"Block {block} is not multiple of blocksize.")
        self.pos += len(data)
        self.end = self.pos
        return len(data)

    # Data must a multiple of blocksize or less than blocksize
    # If len(data) < blocksize it must be the last read
    def readinto(self, data: bytearray | memoryview):
        if self.pos == self.end:
            return 0
        block, remainder = divmod(self.pos, self.blocksize)
        if remainder:
            raise ValueError(f"Block {block} read not aligned at block boundary.")
        if len(data) % self.blocksize != 0 and len(data) > self.blocksize:
            raise ValueError(f"Block {block} is not multiple of blocksize.")
        ln, remaining = len(data), self.end - self.pos
        if ln <= remaining:
            self.device.readblocks(block, data)
        else:
            ln = remaining
            mv = memoryview(data)
            self.device.readblocks(block, mv[:ln], 0)
        self.pos += ln
        return ln

    def seek(self, offset: int, whence: int = 0):
        start = [0, self.pos, self.end]
        self.pos = start[whence] + offset


# A simple class to wrap a Blockdev object with buffered writes
class BufferedBlockdev(Blockdev):
    def __init__(self, device: Blockdev, size: int = 0, verbose: bool = True):
        super().__init__(device, verbose)
        size = size or self.blocksize
        if size < self.blocksize or size % self.blocksize != 0:
            raise ValueError(f"size must be multiple of blocksize ({self.blocksize})")
        self._mv = memoryview(bytearray(size))
        self._bufp: int = 0
        self.sha = hashlib.sha256()

    def flush(self) -> None:
        if self._bufp:
            mv = self._mv[: self._bufp]
            super().write(mv)
            self.sha.update(mv)  # Maintain a hash of bytes written to device
            self._bufp = 0

    def write(self, data: bytearray | memoryview) -> int:
        data_mv = memoryview(data)  # Avoid allocating memory
        data_in, data_len = 0, len(data)
        while data_in < data_len:
            # Copy as much data as will fit in the rest of the buffer
            ln = min(len(self._mv) - self._bufp, data_len - data_in)
            self._mv[self._bufp : self._bufp + ln] = data_mv[data_in : data_in + ln]
            self._bufp += ln
            if self._bufp == len(self._mv):
                self.flush()
            data_in += ln
        return len(data)

    # Append data from f to the block device
    def write_file(self, f) -> int:
        start = self.pos
        while (n := f.readinto(self._mv[self._bufp :])) != 0:
            self._bufp += n
            if self._bufp == len(self._mv):
                self.flush()
        return self.pos - start


# BlockdevWriter provides a convenient interface to writing images to any
# block device which implements the os.AbstractBlockDev interface.
# (eg. Partition on flash storage on ESP32)
class BlockDevWriter:
    def __init__(
        self,
        device,  # Block device to recieve the data (eg. esp32.Partition)
        sha: str | bytes = "",  # The expected hash of the data to be written
        length: int = 0,  # Expected length of the data to be written
        verify: bool = True,  # Should we read back and verify data after writing
        verbose: bool = True,  # Print out details and progress
    ):
        self.device = BufferedBlockdev(device)
        self.sha_check = str(sha)
        self._length = length
        self._verify = verify
        self._verbose = verbose
        self.sha: str = ""

        blocksize, blockcount = self.device.blocksize, self.device.blockcount
        if length > blocksize * blockcount:
            raise ValueError(f"length ({length} bytes) is > size of partition.")
        self.print(f"Device: {blockcount} x {blocksize} byte blocks.")
        if length:
            blocks, remainder = divmod(length, blocksize)
            self.print(f"Writing {blocks} blocks + {remainder} bytes.")

    def print(self, *args, **kwargs) -> None:
        if self._verbose:
            print(*args, **kwargs)

    # Append data to the block device
    def write(self, data: bytearray) -> int:
        return self.device.write(data)

    # Append data to the block device
    def write_file(self, f) -> int:
        return self.device.write_file(f)

    # Flush remaining data to the block device and confirm all checksums
    # Raises:
    #   ValueError("SHA mismatch...") if SHA != provided sha
    #   ValueError("SHA verify fail...") if verified SHA != written sha
    def close(self) -> bool:
        self.device.flush()  # Flush data in buffer to device
        self.print()
        # Check the checksums (SHA256)
        self.sha = binascii.hexlify(self.device.sha.digest()).decode()
        bytes_written = self.device.size()
        if self._length and self._length != bytes_written:
            raise ValueError(f"Receive {bytes_written} bytes (expect {self._length}).")
        if self.sha_check and self.sha_check != self.sha:
            raise ValueError(f"SHA mismatch recv={self.sha} expect={self.sha_check}.")
        if self._verify:
            self.verify()
        if self._verbose or not self.sha_check:
            print(f"SHA256={self.sha}")
        self.device.seek(0)  # Reset to start of partition
        return (bytes_written, self.sha)

    # Read back the data we have written to the partition and check the
    # checksums. Must be called from, or after, close().
    def verify(self) -> str | None:
        self.device.seek(0)  # Reset to start of partition
        blocks, remainder = divmod(self.device.size(), self.device.blocksize)
        self.print(f"Verifying {blocks} blocks + {remainder} bytes...", end="")
        mv = memoryview(bytearray(self.device.blocksize))
        read_sha = hashlib.sha256()
        while (n := self.device.readinto(mv)) > 0:
            read_sha.update(mv[:n])
        # Check the read and write checksums
        read_sha = binascii.hexlify(read_sha.digest()).decode()
        if read_sha != self.sha:
            raise ValueError(f"SHA verify failed: write={self.sha} read={read_sha}")
        self.print("Passed.")
        return read_sha

    def __enter__(self):
        return self

    def __exit__(self, e_t, e_v, e_tr):
        if e_t is None:
            self.close()
