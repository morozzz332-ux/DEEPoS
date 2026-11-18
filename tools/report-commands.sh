# Commands sent to the DEEPoS USB console (plink -serial ... -m this-file).
# The shell is ash from busybox; keep one command per line.
echo "===== uname ====="
uname -a
echo "===== cmdline ====="
cat /proc/cmdline
echo "===== mounts ====="
cat /proc/mounts
echo "===== memory ====="
free -m
cat /proc/pressure/memory 2>/dev/null
echo "===== temps ====="
for z in /sys/class/thermal/thermal_zone*; do echo "$(cat $z/type): $(( $(cat $z/temp) / 1000 )) C"; done
echo "===== cpu ====="
cat /sys/devices/system/cpu/cpufreq/policy0/scaling_cur_freq
cat /sys/devices/system/cpu/cpufreq/policy0/scaling_governor
cat /sys/class/devfreq/ff400000.gpu/cur_freq 2>/dev/null
echo "===== modules ====="
ls -l /data/modules 2>/dev/null
echo "===== ab ====="
/usr/bin/updatr --state /data status 2>/dev/null
echo "===== selftest ====="
/usr/bin/launcher --selftest
echo "===== partitions ====="
cat /proc/partitions
echo "===== dmesg tail ====="
dmesg | grep -iE "mmc|panel|st7703|rk817|gadget|drm" | tail -n 60
echo "===== done ====="
