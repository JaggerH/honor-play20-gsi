# 逐步流程

适用：荣耀畅玩20 KOZ-AL00，固件 4.0.0.292，Windows 主机 + WSL。其它展锐 T610/ums512 + 华为/荣耀 uboot 的机器可以参照，但**每个偏移量、分区布局都必须先在自己的设备上读出来再算**，不要照抄数字。

所有 spd_dump 命令都在 Windows 侧运行（通过 WSL 调用 `spd_dump.exe`），文件路径用 Windows 路径。大文件放在 Windows 本地盘，不要放 `\\wsl.localhost`。

约定：下文 `CONNECT` 代表

```
spd_dump.exe --wait 60 exec_addr 0x3ee8 fdl <fdl1> 0x5500 fdl <fdl2> 0x9efffe00 exec slot 1 path <备份目录>
```

`slot 1` 只是让 spd_dump 不要对非 A/B 的 `xxx/xxx_bak` 分区对做隐式处理，不会改 A/B 状态。

## 0. 准备

- 安装展锐 USB 驱动（`sprdvcom.inf`，BootROM 设备是 `VID_1782&PID_4D00`，显示为 `SPRD U2S Diag (COMx)`）。
- spd_dump：<https://github.com/TomKing062/spreadtrum_flash>
- FDL1/FDL2 与签名绕过：<https://github.com/TomKing062/unisoc_chipram_signcheck_exploit> 和 spreadtrum_flash 的说明。
  本机实测要点：RAM 里的 FDL1 证书要换成**原厂 SPL 的根公钥证书**，否则往 splloader/uboot 写入时，最后一包会以 `usb_send failed` 失败（FDL2 用 RAM 中 FDL1 的公钥校验传入的 SPL）。只改 RAM 里的副本，不写入闪存。
- **先备份**：`r uboot r uboot_bak r boot r ramdisk r vbmeta r vbmeta_bak r dtbo r persist r misc r reserved3`，以及 super 前 2 MiB（`read_part super 0 0x200000 super_head.bin`）。persist 只要执行一次 `e userdata` 就会被擦掉。

## 1. 进入 BootROM 下载模式

- 系统能开机时：`adb reboot autodloader`。**注意：这会清空 splloader 和 splloader_bak**，从此每次开机都要靠电脑把 SPL 送进内存，直到第 8 步写回为止。
- SPL 为空时，开机就会自动进入 BootROM，屏幕保持全黑。
- 在 BootROM 里不会充电。待太久电池会耗尽，表现是“接入音后马上断开”。用壁式充电器充 40 分钟以上再试。
- 某个 USB 口反复复位后，可能卡在“设备描述符请求失败”，换个口就好。

## 2. 用 SPL 内存启动（SPL 为空期间每次开机都要做）

```
spd_dump.exe --wait 20 fdl stock-spl-signed.bin 0x5500
```

日志结尾出现 `EXEC FDL1 / CHECK_BAUD FAIL` 是正常的：SPL 已经执行，USB 随之断开。

## 3. uboot：让锁状态返回 unlocked

用 unisoc_chipram_signcheck_exploit 的 **Patch-Post-Verification**（magic64 + difftool）：保留原厂签名载荷和证书不变，在运行时把 `get_lock_state_for_verifyboot` 依赖的 helper 改成恒返回 1（PHONE Unlocked）。在 4.0.0.292 上，这个 helper 位于 uboot 文件偏移 0x57d74，运行时地址 0x9f057b74，补丁共 8 字节。其它版本要按函数体特征重新定位，**不要套用公开旧版的硬编码偏移**。

写入 `uboot` 和 `uboot_bak`，回读核对。成功的标志：开机出现 “Your device has been unlocked and can be trusted” 警告，uboot_log 里出现 `androidboot.vbmeta.device_state=unlocked`。

## 4. boot：去掉 first-stage fstab 的 avb

```
python3 tools/patch_boot_dtb_fstab.py boot.bin boot-noavb.bin
CONNECT w boot boot-noavb.bin r boot reset
```

vbmeta 保持原厂，**不要**改 flags（原因见 README）。

## 5. vendor：关闭 /data 加密

```
CONNECT read_part super <vendor_first_sector*512> <vendor_sectors*512> vendor.img reset
python3 tools/patch_vendor_fstab.py vendor.img <super_size> <vendor_first_sector*512> vendor-fstab.sparse.img
CONNECT w super vendor-fstab.sparse.img read_part super <回显的偏移> 4096 check.bin reset
```

扇区数用 `python3 tools/lp_meta.py super_head.bin` 查看。

## 6. 需要时扩大 system

GSI 解压后比 system extent 大时：

```
python3 tools/lp_grow.py super_head.bin system hw_product <super_size> super_head-new.bin lp.sparse.img
```

## 7. 写入 GSI 并清数据

```
python3 tools/mk_super_sparse.py gsi.img gsi.sparse.img <super_size> <system_first_sector*512>
python3 tools/verify_sparse.py gsi.sparse.img gsi.img <system_first_sector*512>
CONNECT w super lp.sparse.img w super gsi.sparse.img read_part super ... e userdata r misc reset
```

然后启动两次（第 2 步）：第一次进原厂 recovery 执行 `--wipe_data`，结束后自动回到 BootROM；第二次启动 GSI。

如果出现 Restart / Factory reset / Wipe cache / Safe mode 界面，说明 Android 写了 `--prompt_and_wipe_data`。读 misc 看 `--reason=`，修正后用 2048 字节全零覆盖 misc 开头（`wof misc 0 zero2k.bin`）。

## 8. 写回 SPL，脱离电脑

```
CONNECT w splloader stock-spl-signed.bin w splloader_bak stock-spl-signed.bin r splloader r splloader_bak reset
```

回读两份，签名部分应与原文件一致，其余填充为 0。复位后手机应能自行启动。再拔线做一次关机、开机验证。

## 调试

见 README 的“调试手段”一节和 [debug/](../debug/)。uboot 自己的日志在 `uboot_log` 分区（多条 0x40000 大小的环形记录，不按时间排序，看 `boot count` 字段）。华为 recovery 的日志在 `log` 分区（ext4，可用 debugfs `rdump` 导出，`recovery/last_kmsg*` 是 gzip 压缩的，且是 recovery 自己的内核日志）。
