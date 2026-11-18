set -e
cd /w
# stale aarch64 objects from the cross build break the host link
make -C apps/launcher clean >/dev/null 2>&1 || true
python3 tests/run.py    | grep -E "^(PASS|FAIL)"
python3 tests/selftest_test.py | grep -E "^(PASS|FAIL)"
python3 tests/input_test.py
python3 tests/display_test.py
python3 tests/launcher_mod_test.py
python3 tests/board_test.py   | grep -E "^(PASS|FAIL)"
python3 tests/image_test.py   | grep -E "^(PASS|FAIL)"
python3 tests/modd_test.py    | grep -E "^(PASS|FAIL)"
python3 tests/saved_test.py   | grep -E "^(PASS|FAIL)"
python3 tests/modules_test.py | grep -E "^(PASS|FAIL)"
python3 tests/boot_test.py    | grep -E "^(PASS|FAIL)"
python3 tests/updatr_test.py  | grep -E "^(PASS|FAIL)"
python3 tests/launch_test.py  | grep -E "^(PASS|FAIL)"
python3 tests/config_test.py | grep -E "^(PASS|FAIL)"
