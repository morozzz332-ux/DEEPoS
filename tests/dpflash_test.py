import gzip
import hashlib
import os
import pathlib
import struct
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "tools"))
import dpflash


class FlashTest(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.image = pathlib.Path(folder.name) / "image.img"
        self.card = pathlib.Path(folder.name) / "card.img"
        self.data = bytes(range(256)) * (3 * dpflash.MIB // 256)
        self.image.write_bytes(self.data)
        self.card.write_bytes(b"\xa5" * (len(self.data) + dpflash.MIB))

    def test_interrupted_write_stays_unpublished_and_can_resume(self):
        original = dpflash.write_at
        writes = []

        def interrupt(handle, offset, data, *args, **kwargs):
            writes.append(offset)
            if offset == 2 * dpflash.MIB:
                raise OSError("simulated interruption")
            original(handle, offset, data, *args, **kwargs)

        with patch.object(dpflash, "write_at", side_effect=interrupt):
            with self.assertRaisesRegex(OSError, "simulated interruption"):
                dpflash.flash(self.image, self.card)
        contents = self.card.read_bytes()
        self.assertEqual(contents[:dpflash.TABLE_BYTES], bytes(dpflash.TABLE_BYTES))
        self.assertEqual(contents[dpflash.TABLE_BYTES:dpflash.MIB],
                         self.data[dpflash.TABLE_BYTES:dpflash.MIB])
        self.assertIn(dpflash.MIB, writes)

        expected = hashlib.sha256(self.data).hexdigest()
        with patch.object(dpflash, "write_at", wraps=original) as write_at:
            dpflash.flash(self.image, self.card, expected_sha=expected, resume=True, verify=True)
        resumed_offsets = [call.args[1] for call in write_at.call_args_list]
        self.assertNotIn(dpflash.MIB, resumed_offsets)
        self.assertEqual(resumed_offsets[-1], 0)
        self.assertEqual(dpflash.hash_target(self.card, len(self.data)), expected)

    def test_invalid_checksum_leaves_target_unchanged(self):
        initial = self.card.read_bytes()
        with self.assertRaises(SystemExit):
            dpflash.flash(self.image, self.card, expected_sha="0" * 64)
        self.assertEqual(self.card.read_bytes(), initial)

    def test_gzip_writes_decoded_bytes_and_checks_the_decoded_digest(self):
        packed = self.image.with_suffix(".img.gz")
        packed.write_bytes(gzip.compress(self.data))
        expected = hashlib.sha256(self.data).hexdigest()
        self.assertEqual(dpflash.main(["--inspect-image", "--image", str(packed),
                                      "--expect-sha256", expected]), 0)
        dpflash.flash(packed, self.card, expected_sha=expected, verify=True)
        self.assertEqual(dpflash.hash_target(self.card, len(self.data)), expected)

    def test_truncated_gzip_leaves_target_unchanged(self):
        packed = self.image.with_suffix(".img.gz")
        packed.write_bytes(gzip.compress(self.data)[:-4])
        initial = self.card.read_bytes()
        self.assertEqual(dpflash.main(["--image", str(packed), "--target", str(self.card)]), 1)
        self.assertEqual(self.card.read_bytes(), initial)

    def test_short_read_is_error(self):
        with self.card.open("rb") as handle:
            with self.assertRaisesRegex(OSError, "expected 1024"):
                dpflash.read_at(handle, self.card.stat().st_size - 512, 1024)

    def test_blank_mbr_with_four_unused_driver_entries(self):
        size = 31104958464
        layout = bytearray(48 + 4 * 144)
        struct.pack_into("<II", layout, 0, 0, 4)
        mbr = bytearray(512)
        with patch.object(dpflash, "_device_ioctl", side_effect=[
                struct.pack("<Q", size), layout]), patch.object(dpflash, "read_at", return_value=mbr):
            dpflash._require_blank_disk(1, size)

        mbr[450] = 0x0C
        with patch.object(dpflash, "_device_ioctl", side_effect=[
                struct.pack("<Q", size), layout]), patch.object(dpflash, "read_at", return_value=mbr):
            with self.assertRaisesRegex(OSError, "expected a blank raw disk"):
                dpflash._require_blank_disk(1, size)

        struct.pack_into("<q", layout, 48 + 16, 1024)
        with patch.object(dpflash, "_device_ioctl", side_effect=[struct.pack("<Q", size), layout]):
            with self.assertRaisesRegex(OSError, "expected a blank raw disk"):
                dpflash._require_blank_disk(1, size)

    @unittest.skipUnless(os.name == "nt", "requires Windows routing")
    def test_larger_windows_target_publishes_only_relocated_gpt(self):
        disk_size = self.card.stat().st_size
        new_head = b"H" * dpflash.TABLE_BYTES
        new_tail = b"T" * dpflash.BACKUP_BYTES
        module = SimpleNamespace(relocated_metadata=lambda *_: (new_head, new_tail))
        expected = hashlib.sha256(self.data).hexdigest()
        # Route an emulated Windows disk to the ordinary temporary file.
        with patch.dict(sys.modules, {"expand_gpt": module}), \
                patch.object(dpflash, "_checked_disk", return_value=str(self.card)), \
                patch.object(dpflash, "_require_blank_disk"), \
                patch.object(dpflash, "_refresh_windows_disk", create=True) as refresh:
            dpflash.flash(self.image, r"\\.\PhysicalDrive2", expected_sha=expected,
                          disk_path="emulated", disk_size=disk_size)
        refresh.assert_called_once_with(str(self.card))
        card = self.card.read_bytes()
        self.assertEqual(card[:dpflash.TABLE_BYTES], new_head)
        self.assertEqual(card[-dpflash.BACKUP_BYTES:], new_tail)
        tail_offset = len(self.data) - dpflash.BACKUP_BYTES
        self.assertEqual(card[dpflash.TABLE_BYTES:tail_offset],
                         self.data[dpflash.TABLE_BYTES:tail_offset])
        self.assertEqual(card[tail_offset:len(self.data)], bytes(dpflash.BACKUP_BYTES))

    @unittest.skipUnless(os.name == "nt", "requires Win32")
    def test_win32_transfers_and_flush_at_64_bit_offset(self):
        # Use a temporary sparse file to verify the Win32 LARGE_INTEGER ABI.
        offset = 4 * dpflash.MIB * 1024 + 512
        handle = dpflash._open_windows(str(self.card), write=True)
        try:
            code = 0x900C4  # FSCTL_SET_SPARSE
            returned = dpflash.wintypes.DWORD()
            if not dpflash.kernel.DeviceIoControl(handle, code, None, 0, None, 0,
                                                  dpflash.ctypes.byref(returned), None):
                self.skipTest("temporary filesystem cannot create sparse files")
            block = b"\x00\xff" * 256
            dpflash.write_at(handle, offset, block)
            dpflash.flush(handle)
            self.assertEqual(dpflash.read_at(handle, offset, len(block)), block)
            with self.assertRaisesRegex(OSError, "expected 1024"):
                dpflash.read_at(handle, offset, 1024)
        finally:
            dpflash.close(handle)


if __name__ == "__main__":
    unittest.main()
