# 无串口、无 adb 的早期启动日志采集

把这两个文件注入 GSI 的 system 镜像（ext4，用 `debugfs -w`）：

```
cd /system/etc/init
write zzdbg.rc zzdbg.rc
sif zzdbg.rc mode 0100644
ea_set -f label_system_file zzdbg.rc security.selinux     # "u:object_r:system_file:s0\0"
cd /system/etc
write zzdbg.sh zzdbg.sh
sif zzdbg.sh mode 0100755
ea_set -f label_system_file zzdbg.sh security.selinux
```

- `zzdbg.rc` 用 `seclabel u:r:phhsu_daemon:s0`。TrebleDroid/phh 系 GSI 里，这个域是 permissive 的，init 也允许切换进去。没有这个域的 GSI，需要另找一个 permissive 域；实在不行，就往 `plat_sepolicy.cil` 末尾加 `(typepermissive init)` 并用 su 域，同时把该文件的标签恢复为 `sepolicy_file`。
- `zzdbg.sh` 把日志写进 `/dev/block/by-name/reserved3`。**先确认目标分区确实没被使用（全零），并做好备份**，按自己的设备换成合适的分区。
- 日志持续写入会磨损 eMMC。排查完后务必换回干净镜像，并把分区恢复原状。
- 读回：`spd_dump ... r reserved3`，取到 `=== ZZDBG END` 为止。
