#!/system/bin/sh
trap "" TERM HUP INT
dmesg -w > /dev/zzdm.txt 2>&1 &
lc=0; i=0
while true; do
  i=$((i+1))
  if [ $lc = 0 ] && [ -e /dev/socket/logdr ]; then logcat -b all -v uptime > /dev/zzlc.txt 2>&1 & lc=1; fi
  {
    echo "=== ZZDBG iter $i uptime $(cat /proc/uptime)"
    echo "=== props"; getprop | grep -E "init.svc|crypto|vold|keymaster|keystore|boot|sys.usb|hardware" 
    echo "=== logcat"; tail -c 1500000 /dev/zzlc.txt 2>/dev/null
    echo "=== dmesg"; tail -c 2500000 /dev/zzdm.txt 2>/dev/null
    echo "=== ZZDBG END"
  } > /dev/zzdbg.cut 2>&1
  dd if=/dev/zzdbg.cut of=/dev/block/by-name/reserved3 bs=65536 conv=fsync 2>/dev/null
  sleep 0.3
done
