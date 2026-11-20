set -e
cd /w
# stale aarch64 objects from the cross build break the host link
make -C apps/launcher clean >/dev/null 2>&1 || true
python3 tests/run.py
python3 tests/selftest_test.py
python3 tests/input_test.py
python3 tests/display_test.py
python3 tests/launcher_mod_test.py
python3 tests/board_test.py
python3 tests/image_test.py
python3 tests/dpflash_test.py
python3 tests/modd_test.py
python3 tests/saved_test.py
python3 tests/modules_test.py
python3 tests/boot_test.py
python3 tests/updatr_test.py
python3 tests/launch_test.py
python3 tests/config_test.py
python3 tests/settings_test.py
python3 tests/bios_test.py
python3 tests/playdemo_test.py
python3 tests/preflight_test.py
python3 tests/release_test.py
python3 tests/hardware_test.py
python3 tests/expand_test.py
python3 tests/verify_card_test.py
python3 tests/read_report_test.py
