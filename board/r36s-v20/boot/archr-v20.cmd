# Use the donor's MMC device and the same trace buffer that worked on the V20.
# Complete the marker before sysboot can reuse the U-Boot file size variable.
setenv kernel_addr_r 0x09000000
setenv trace_stage before_sysboot
if env export -t 0x00800800 trace_stage; then
    fatwrite ${devtype} ${devnum}:${distro_bootpart} 0x00800800 /BOOTDIAG.TXT ${filesize}
fi
sysboot ${devtype} ${devnum}:${distro_bootpart} any 0x100000 /extlinux/extlinux.conf
setenv trace_stage sysboot_returned
if env export -t 0x00800800 trace_stage; then
    fatwrite ${devtype} ${devnum}:${distro_bootpart} 0x00800800 /BOOTDIAG.TXT ${filesize}
fi
false
