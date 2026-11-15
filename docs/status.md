# 状态（2026-11-15）

设备：荣耀畅玩20 KOZ-AL00，固件 4.0.0.292（Android 10，Magic UI 4.0），T610 / ums512，内核 4.14。

## 已验证

- LineageOS 23.2（Android 16 QPR2，GAPPS EXT4，2026-05-24，[MisterZtr](https://github.com/MisterZtr/LineageOS_gsi)）能进开机向导和桌面，Google 服务可用。
- 拔掉 USB 线后关机再开机，能独立启动。解锁警告页停留约 30 秒，之后进系统。
- phh v416 Android 12 vanilla 也能进桌面（中间验证用）。

## 代价与已知问题

- **/data 不加密**。要恢复加密，需要给 vold 打补丁，让它忽略 `fscrypt-provisioning` key 插入失败。这个内核不支持该 key 类型。
- **persist 分区被擦**（spd_dump `e userdata` 的副作用）。传感器校准一类数据可能丢失，具体影响还没评估。
- `hw_product` 变为零长度。华为自家的 product 内容对 GSI 无用，但恢复原厂系统前，必须先写回原始 LP 元数据。
- Android 12 phh 版启动后屏幕会熄灭，需要按电源键唤醒。Android 16 上还没观察。
- Windows 能识别到 GSI 的 ADB 接口（`VID_18D1&PID_4EE8`，WinUSB），但 `adb devices` 列表为空，原因未查。
- 每次开机都会显示解锁警告页。

## 没做/没验证

- Android 17：Google 官方 GSI 需要接受 Early Access 协议（限“测试应用兼容性”用途），没有采用。
- 再次进入下载模式的按键组合（音量键 + 插 USB）没验证。目前已知可靠的方法是 `adb reboot autodloader`，但它会清空 SPL。
- 恢复原厂系统的完整回滚流程没有实测。
