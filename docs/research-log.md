# 研究过程（2026-11-15，一天）

按时间顺序记录：每一步的假设、实测结果和证据，**包括走错的路**。路走错的地方，往往正是后来者最容易踩进去的坑。

日志摘录已去掉设备序列号等个人信息。研究由 AI 编码助手（先 Codex，后 Claude）在机主监督下完成，每一次写入闪存都经过回读核对。机主是在手机上看屏幕、按键的那个人。

---

## 第 0 阶段：确认没有官方路径

- Windows 识别到的是荣耀畅玩20（KOZ-AL00），系统 Magic UI 4.0.0.292，Android 10。
- 荣耀官方维护人员 2025 年 10 月明确回复：这款机型“暂无大版本升级计划”。
- 容易混淆的一点：**畅玩20a** 出厂就是 Magic UI 6.1，但那是另一款机型，固件不能互刷。
- 目标改为：系统品牌不限，只要能跑 Android 12 或更高。

## 第 1 阶段：可行性检查（只读）

开启 USB 调试后读到的实机信息：ARM64、6GB 内存、VNDK 29、Treble 和动态分区都支持、system 分区 2.4GB、super 分区 5.6GB；bootloader 处于锁定状态，没有 DSU。

- fastboot 的通用命令和 `oem pull` 都被拒绝，只有华为自家的几条只读 OEM 命令可用（`get-bootinfo` 等）。
- 找到一个同型号的公开项目 [honor-play-20-phone-rescue-kit](https://github.com/Lyotoc/honor-play-20-phone-rescue-kit)：它能做到软解锁和 Root，但每次冷启动都要接电脑辅助，而且用的是旧版本固件。
- 安装展锐下载驱动（`sprdvcom.inf`，带微软 WHCP 签名），手机以 `SPRD U2S Diag` 的身份出现。用 spd_dump 配合补过的 FDL，只读备份了 uboot、boot、ramdisk、vbmeta 和 uboot_log。
- 关键结论：这台 .292 的 uboot 编译于 2026 年 4 月，**和公开的 2021 年版本不一样**，公开项目里写死的偏移量不能直接套用。

## 第 2 阶段：意外 —— `adb reboot autodloader` 清空了 SPL

当时以为这只是一个“重启进下载模式”的普通命令。实际上它在展锐 u-boot15 里的实现是 `erase_spl_enter_download_mode()`：**先擦掉 splloader 和 splloader_bak 两份 SPL**，再进 BootROM。从那以后，手机只能靠电脑把 SPL 送进内存才能开机。

修复过程：
- 把一份原厂签名的 SPL 送进内存，能启动原系统。
- 想把 SPL 写回闪存，两次都在最后一包失败：`usb_send failed (0 / 8200)`。
- 原因：FDL2 会用内存里 FDL1 的根公钥去校验传入的 SPL，而通用补丁版 FDL1 带的是另一把公钥。把**内存里** FDL1 的证书换成荣耀原厂 SPL 的根证书后（可执行部分不变，也不写入闪存），两份 SPL 都写入成功，回读逐字节一致。
- 拔线冷启动验证通过。

> 教训：这台机器上的 `autodloader` 是有破坏性的。后面的实验里，我们反而刻意利用了“SPL 为空”这个状态：每次开机都会落回 BootROM，刷坏了也一定救得回来。等全部做完，再把 SPL 写回去。

## 第 3 阶段：解锁 uboot

- 方法：[unisoc_chipram_signcheck_exploit](https://github.com/TomKing062/unisoc_chipram_signcheck_exploit) 的 Patch-Post-Verification。原厂签名的载荷和证书都不动，签名校验通过之后，再在运行时打补丁。
- 补丁目标：`get_lock_state_for_verifyboot` 依赖的那个 helper（.292 上位于文件偏移 0x57d74，与公开旧版的函数体逐条一致，只有一条 BL 的跳转地址不同），让它恒返回 1（PHONE Unlocked）。公开版里顺带的 LCD-ID 补丁没有照搬。
- 第一次启动：出现解锁警告，然后停在 “Your device is booting now” **十分钟**。
- 读 uboot_log：AVB 已经走到交给内核那一步，所以 uboot 补丁本身没问题。

## 第 4 阶段：原系统在解锁状态下卡住 → 旧加密数据

- 擦除 metadata，并让原厂 recovery 执行 `--wipe_data`。
- 之后原系统能进开机向导。旧日志里有原系统 zygote 的崩溃：`Error creating cache dir /data/dalvik-cache/arm : Required key not available`。推测是锁状态变化后，keymaster 派生出的密钥变了，旧的 FBE 数据解不开（这条没有进一步验证）。
- 坑：spd_dump 的 `e userdata` 并不直接擦 userdata，而是往 misc 写一条清数据命令，然后**擦除 persist 分区**。我们因此丢了 persist，而且事先没有备份。

## 第 5 阶段：刷 GSI（phh Android 12）—— 刷写工具本身

- `wof`（按偏移写）在大于 4 GiB 的 super 上直接拒绝，而且它是 32 位程序，没法整块读入 1.8GB 的镜像。
- 改用 sparse 镜像，读 FDL2 的源码确认了两点：
  - 它按 magic 自动识别 sparse 格式，支持 DONT_CARE；
  - **如果第一个 chunk 不是 DONT_CARE，会先擦掉整个目标分区**（这是为 `fastboot flash -S` 设计的行为）。
- 于是 sparse 镜像的结构是：[0, 2MB) 标成 DONT_CARE，跳过 LP 元数据；system 那一段是 RAW，全零块用 FILL；其余全部 DONT_CARE。只改写 system 这一段，vendor 和 LP 元数据完全不碰。

## 第 6 阶段：vbmeta 的两个死胡同

**flags=3**（同时关闭 verity 和 verification）：uboot 直接崩溃。

```
avb_slot_verify.c:894: DEBUG: vbmeta: VERIFICATION_DISABLED bit is set.
"Synchronous Abort" handler, esr 0x8600000d
ELR:     0
```

ELR 为 0 表示调用了空函数指针。libavb 的 VERIFICATION_DISABLED 分支会调用 `ops->get_size_of_partition`，这个 uboot 没有实现它。随后华为的 bootfail 机制把 misc 改成了 `boot-erecovery`。

**flags=1**（只关闭 verity）：uboot 放行了，`HASH_MISMATCH` 在解锁状态下被允许，命令行里也出现了 `androidboot.veritymode=disabled`。但 GSI 每次大约 2 分钟后就复位，USB 始终没有出现，注入的日志服务一行都没写出来，说明 GSI 的 init 根本没有启动。

决定性的线索：改 vbmeta 前后，命令行里的 `androidboot.vbmeta.digest` **始终是同一个原厂值**。Android 10 第一阶段 init（原厂 ramdisk 里的 libfs_avb）会用磁盘上的 vbmeta 重新计算 digest，与命令行比对，对不上就失败，报 `Failed to mount required partitions early`。recovery 之所以不受影响，是因为它直接跳过第一阶段挂载（日志里是 `First stage mount skipped (recovery mode)`）。

**解法**：vbmeta 保持原厂，这样 digest 就对得上；把 boot 镜像 dtb 里 `/firmware/android/fstab` 各条目的 `avb` 原位改成 `zzz`，一共 18 处、54 字节。第一阶段于是不再调用 AvbHandle，也就不再比对 digest；fs_mgr 对不认识的标志只打一条警告。

## 第 7 阶段：没有串口、没有 adb，怎么看日志

- 尝试过 ramoops：dtb 里有 `ramoops@fff80000`，但 FDL2 不支持 `read_mem`（返回 0xfe）；在 FDL1 阶段读则超时，手机还得强制断电才能恢复。
- `log` 分区（华为的 ext4 日志盘）里，`recovery/last_kmsg*` 是 gzip 压缩的，**记录的是 recovery 自己的内核日志**，不是上一次启动的。
- 最后有效的办法：往 GSI 的 system 镜像里注入一个 init 服务（`debugfs -w`，见 [debug/](../debug/)），把 dmesg 和 logcat 持续 `dd` 到一个全零的空闲分区 `reserved3`。前后改了三版：
  1. 每 4 秒写一次：只抓到第 30 秒，故障发生之后的部分全丢了；
  2. 后台流式采集、每秒写一次：仍然丢失，因为 init 关机时先给所有服务发 SIGTERM，采集脚本也被杀了；
  3. `trap "" TERM`，并把间隔缩到 0.3 秒：终于抓到了 init 关机前的最后几行。
- 中途误判过一次：日志停在 phh `rw-system.sh` 执行 `find` 的时候，于是怀疑遍历 `/sys` 卡死了内核。后来证明这只是时间上的巧合，真正的原因在下一阶段。

## 第 8 阶段：FBE —— Android 12 及以上的 vold 遇上 4.14 内核

misc 里留下了失败原因：

```
boot-recovery
recovery
--prompt_and_wipe_data
--reason=enablefilecrypto_failed
```

（屏幕上看到的就是 Restart / Factory reset / Wipe cache / Safe mode 那个界面。）

vold 的日志：

```
I vold: fscrypt_initialize_systemwide_keys
D vold: Installed fscrypt key with ref 22e2ada8b1c58169 to /data
E vold: Failed to insert fscrypt-provisioning key for 22e2ada8b1c58169 into session keyring: No such device
```

这个内核支持 `FS_IOC_ADD_ENCRYPTION_KEY`，所以 vold 走的是新路径；但它不支持 `fscrypt-provisioning` 这种密钥类型（dmesg 里只注册了 `.fscrypt` 和 `._fscrypt`）。改成 v2 加密策略（`aes-256-xts:aes-256-cts:v2`）后，同样的位置以同样的方式失败。

解法：在 vendor fstab 里去掉 `fileencryption=`，代价是 /data 不加密。vendor 分区是 erofs，fstab 那一行是未压缩的明文，所以可以原位改写，空出来的位置补空格保持长度不变；只需要一个 4KB 的块补丁。之后每改一次都要重新清数据。

**结果：phh Android 12 进入桌面。**（屏幕一开始是熄灭的，按电源键才看到。）

## 第 9 阶段：Android 16（带 Google 服务）

- 机主问：能不能直接上 Android 17？Google 官方确实有 Android 17 的 GSI，但下载前必须接受 Early Access 协议，协议限定只能用于“测试应用兼容性”，最终没有采用。
- 选了 [MisterZtr 的 LineageOS 23.2](https://github.com/MisterZtr/LineageOS_gsi)（Android 16 QPR2）GAPPS **EXT4** 版。EROFS 版删掉了 VNDK 28/29，而且要求 5.4 以上的内核。
- 镜像约 3.3GB，system 只有 2.4GB。super 里 system 后面紧挨着华为的 `hw_product`（1.6GB），而 Android 12 的日志显示它在第一阶段本来就挂载失败，系统照样能用。于是改写 LP 元数据（自己写的解析器，按 liblp 格式，主副两份都改并重算 SHA-256）：system 扩到 4.19GB，hw_product 改为零长度。
- 写入方式同样是以 DONT_CARE 开头的 sparse 镜像。注意 LP 元数据从第 1 个 4K 块开始，第 0 块必须保持 DONT_CARE，否则 FDL2 会先把整个 super 擦掉。
- 调试日志服务换成 phh 的 `phhsu_daemon` 域（permissive，且 init 允许切换进去），这样不需要改 init 的 SELinux。
- **结果：一次就进了开机向导。**

## 第 10 阶段：收尾，以及最后的意外

- 换回干净的 Lineage 镜像，reserved3 恢复为全零，两份原厂签名 SPL 写回闪存。
- 意外一：手机在 BootROM 里待了几个小时，**电池耗尽**了（这个模式下软件不管充电）。表现是插上后响一声接入音，紧接着又断开。用壁式充电器充了 40 分钟。
- 意外二：Windows 上用了一整天的那个 USB 口卡在“设备描述符请求失败”，**换一个口就好了**。
- 最终验证：拔掉 USB 线，关机，再开机。解锁警告页停留约 30 秒，然后进入 Android 16 桌面。

## 未完成

见 [status.md](status.md)。其中最值得做的是给 vold 打补丁，恢复 /data 加密。
