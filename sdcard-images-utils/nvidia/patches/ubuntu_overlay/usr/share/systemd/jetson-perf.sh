#!/bin/bash

#Set the power model to MAXN SUPER
nvpmodel -m 2
jetson_clocks

# Lock camera subsystem clocks
echo 1 > /sys/kernel/debug/bpmp/debug/clk/vi/mrq_rate_locked
echo 1 > /sys/kernel/debug/bpmp/debug/clk/isp/mrq_rate_locked
echo 1 > /sys/kernel/debug/bpmp/debug/clk/nvcsi/mrq_rate_locked
echo 1 > /sys/kernel/debug/bpmp/debug/clk/emc/mrq_rate_locked

cat /sys/kernel/debug/bpmp/debug/clk/vi/max_rate > /sys/kernel/debug/bpmp/debug/clk/vi/rate
cat /sys/kernel/debug/bpmp/debug/clk/isp/max_rate > /sys/kernel/debug/bpmp/debug/clk/isp/rate
cat /sys/kernel/debug/bpmp/debug/clk/nvcsi/max_rate > /sys/kernel/debug/bpmp/debug/clk/nvcsi/rate
cat /sys/kernel/debug/bpmp/debug/clk/emc/max_rate > /sys/kernel/debug/bpmp/debug/clk/emc/rate

# Ensure CPU governor is performance
for cpu in /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor; do
    echo performance > $cpu
done

# Debug print at the end
echo "Debug: Jetson Orin Nano clocks locked and CPU governors set to performance."
