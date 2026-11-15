# honor-play20-gsi

在**荣耀畅玩20（KOZ-AL00，紫光展锐 T610 / ums512，Magic UI 4.0，Android 10）**上跑 Android 16 GSI（LineageOS 23.2，带 Google 服务）的完整方法与工具。

官方已明确不提供大版本升级。这个仓库记录了怎样绕过启动链限制，让这台 2021 年的机器用上 Android 16，以及每一处卡点的**根因与证据**，供同平台（展锐 T610/T618/T700 + 华为/荣耀定制 uboot）的机器参考。

> ⚠️ 这是在测试机上完成的实验。会清空数据，会修改启动链，任何一步出错都可能需要 BootROM 下载模式才能救回。本仓库**不含**任何荣耀固件二进制（uboot、SPL、FDL、boot 等），也不含设备 dump。

## 结果

| 项 | 状态 |
|---|---|
| Android 12（phh v416 vanilla） | ✅ 进入桌面 |
| Android 16（LineageOS 23.2 GAPPS EXT4，2026-05-24） | ✅ 进入开机向导/桌面 |
| 脱离电脑冷启动 | 见 [docs/status.md](docs/status.md) |
| /data 加密 | ❌ 已关闭（原因见下） |

## 启动链与每个坑

```
BootROM ──> SPL(splloader, 原厂签名) ──> uboot(打补丁, 签名校验被绕过) ──> kernel 4.14 + ramdisk(原厂)
                                              │                              │
                                              ├─ 读 vbmeta (AVB)             ├─ first-stage: DT fstab 挂 system/vendor
                                              └─ 加载 boot(dtb 里有 fstab)    └─ second-stage: GSI init
```

1. **bootloader 锁**：华为定制 uboot 的锁状态由 `get_lock_state_for_verifyboot` 读取。用上游 [unisoc_chipram_signcheck_exploit](https://github.com/TomKing062/unisoc_chipram_signcheck_exploit) 的“签名后补丁”框架，让该 helper 恒返回 unlocked，原厂签名载荷保持不变。之后 cmdline 变为 `androidboot.vbmeta.device_state=unlocked`。
2. **vbmeta flags 不能改**：
   - flags=3（disable-verification）会让 uboot 崩溃：`"Synchronous Abort" ... ELR: 0`。libavb 的 VERIFICATION_DISABLED 分支会调用 `ops->get_size_of_partition`，而这个 uboot 没实现该回调，是空指针。
   - flags=1（disable-verity）能过 uboot，但 uboot 传给内核的 `androidboot.vbmeta.digest` **仍是原厂值**。Android 10 第一阶段 init 的 libfs_avb 会重算 digest，对不上就报 `Failed to mount required partitions early`，GSI 的 init 根本跑不起来，recovery 却正常（它跳过 first-stage mount），所以很迷惑。
   - **解法**：vbmeta 保持原厂；把 boot 镜像 dtb 里 `/firmware/android/fstab/*/fsmgr_flags` 的 `avb` 原位改成 `zzz`（[tools/patch_boot_dtb_fstab.py](tools/patch_boot_dtb_fstab.py)）。first-stage 不再走 AVB/dm-verity。boot 的 hash 不匹配在解锁状态下被放行。
3. **/data 加密（FBE）失败**：Android 12+ 的 vold 在 `FS_IOC_ADD_ENCRYPTION_KEY` 之后，总会再往 session keyring 插一个 `fscrypt-provisioning` key。这台 4.14 内核支持前者、不支持后者：
   `E vold: Failed to insert fscrypt-provisioning key for ... into session keyring: No such device`
   → `--reason=enablefilecrypto_failed` → 进 recovery 提示清数据（Restart / Factory reset / Wipe cache / Safe mode 界面）。改用 v2 策略同样失败。
   **解法**：在 vendor fstab 里去掉 `fileencryption=`（[tools/patch_vendor_fstab.py](tools/patch_vendor_fstab.py)）。/data 不加密。想保留加密，需要给 GSI 的 vold 打补丁，让它忽略 provisioning key 插入失败（未做）。
4. **system 分区放不下带 GApps 的 GSI**：system 2.4 GB，LineageOS GAPPS EXT4 约 3.3 GB。super 里 system 后面紧挨着华为的 `hw_product`（1.6 GB，GSI 用不到，first-stage 本来就挂不上）。改写 LP 元数据，让 system 吞掉 hw_product，hw_product 变为零长度（[tools/lp_grow.py](tools/lp_grow.py)）。
5. **刷写工具的坑**（[spd_dump / spreadtrum_flash](https://github.com/TomKing062/spreadtrum_flash) + 展锐 FDL2）：
   - `wof`（按偏移写）在大于 4 GiB 的分区上直接拒绝，而且它是 32 位程序，没法整块读入大文件。
   - FDL2 会自动识别 sparse 镜像，**如果第一个 chunk 不是 DONT_CARE，会先擦掉整个目标分区**。本仓库所有 sparse 都以 DONT_CARE 开头，只写需要的块（[tools/mk_super_sparse.py](tools/mk_super_sparse.py)）。
   - `e userdata` 实际做的是：往 misc 写 `--wipe_data`，再**擦除 persist 分区**。动手前先备份 persist！
   - 通过 `adb reboot autodloader` 进下载模式时，会**清空两份 SPL**（`erase_spl_enter_download_mode()`）。之后手机必须靠电脑把 SPL 送进内存才能启动，直到把 SPL 写回。
6. **华为 bootfail 保护**：连续启动失败会自动转进 recovery 或 eRecovery。每次失败后要检查并清空 misc。

## 调试手段：没有串口、没有 adb 时怎么拿日志

GSI 早期启动失败时 USB 还没起来，ramoops 也读不出。做法是往 GSI 的 system 镜像里注入一个 init 服务（[debug/](debug/)）：
- `on early-init` 启动，以 permissive 的 `phhsu_daemon` 域运行（Android 12 phh 镜像需要另外加 `(typepermissive init)`，并用 su 域）；
- 后台运行 `dmesg -w` 和 `logcat -v uptime`，主循环每 0.3 秒把日志尾部 `dd` 到一个空闲的原始分区（这台机器上是全零的 `reserved3`，先备份）；
- 忽略 SIGTERM，这样 init 关机重启前的最后几行也能落盘；
- 下次进下载模式，用 `r reserved3` 读回。

用 `debugfs -w`（`write` / `sif` / `ea_set security.selinux`）直接改 ext4 镜像，不需要 root 挂载。phh 的镜像带 `shared_blocks`，要先 `resize2fs` 扩容，再用 `e2fsck -E unshare_blocks` 解除去重。

## 文档

- [docs/procedure.md](docs/procedure.md)：逐步流程与命令
- [docs/status.md](docs/status.md)：当前状态与未解决问题

## 致谢

- TomKing062：[unisoc_chipram_signcheck_exploit](https://github.com/TomKing062/unisoc_chipram_signcheck_exploit)、CVE-2022-38691/38692 相关工作
- [spreadtrum_flash（spd_dump）](https://github.com/TomKing062/spreadtrum_flash)
- phhusson 的 treble GSI、TrebleDroid、MisterZtr 的 LineageOS GSI
- 早期同型号探索：[honor-play-20-phone-rescue-kit](https://github.com/Lyotoc/honor-play-20-phone-rescue-kit)

## 免责声明

仅供研究与学习。刷机有变砖风险，后果自负。不提供、也不要上传任何受版权保护的厂商固件。
