# Bootstrap extlinux from the device and FAT partition selected by U-Boot.
setenv kernel_addr_r 0x09000000
sysboot ${devtype} ${devnum}:${distro_bootpart} any 0x100000 /extlinux/extlinux.conf
