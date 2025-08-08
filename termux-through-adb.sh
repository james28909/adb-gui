# log into termux shell through adb/busybox and have root priviledges ! :p
setenforce 0 && /data/adb/magisk/busybox sh -c "/system/bin/run-as com.termux /data/data/com.termux/files/usr/bin/bash -c '. /data/data/com.termux/files/usr/etc/termux/termux.env && cd ./files/home && bash --login'"

