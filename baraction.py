#!/usr/bin/env python3
import os
import sys
import time

# ==============================================================================
# USER CONFIGURATION (Change to match your system specs)
# ==============================================================================
IFACE = "ens3"         # Your network interface
DISK_PATH = "/home"    # The drive partition to monitor
INTERVAL = 2.0         # Update interval in seconds
SEPARATOR = " | "      # The divider between bar modules
# ==============================================================================

class SystemMonitor:
    def __init__(self):
        self.iface = IFACE
        self.disk_path = DISK_PATH
        
        self.prev_cpu_idle = 0
        self.prev_cpu_total = 0
        
        self.rx_path = f'/sys/class/net/{self.iface}/statistics/rx_bytes'
        self.tx_path = f'/sys/class/net/{self.iface}/statistics/tx_bytes'
        
        self.prev_time = time.time()
        self.prev_rx_bytes = self._read_sys_int(self.rx_path)
        self.prev_tx_bytes = self._read_sys_int(self.tx_path)
        
        self.temp_path = self._find_cpu_temp_path()

    def _read_sys_file(self, path):
        try:
            with open(path, 'r') as f:
                return f.read()
        except FileNotFoundError:
            return ""

    def _read_sys_int(self, path):
        data = self._read_sys_file(path)
        return int(data.strip()) if data else 0

    def _find_cpu_temp_path(self):
        cpu_drivers = {'k10temp', 'coretemp', 'zenpower', 'cpu_thermal'}
        if os.path.exists('/sys/class/thermal/thermal_zone0/temp'):
            return '/sys/class/thermal/thermal_zone0/temp'
            
        try:
            for d in os.listdir('/sys/class/hwmon'):
                name_file = f'/sys/class/hwmon/{d}/name'
                if os.path.exists(name_file):
                    with open(name_file, 'r') as f:
                        driver_name = f.read().strip()
                    if driver_name in cpu_drivers:
                        target = f'/sys/class/hwmon/{d}/temp1_input'
                        if os.path.exists(target):
                            return target
        except Exception:
            pass
        return None

    def _format_speed(self, bits_per_sec):
        if bits_per_sec >= 1_000_000:
            return f"{bits_per_sec / 1_000_000:.0f}Mbps"
        return f"{bits_per_sec / 1_000:.0f}Kbps"

    def get_uptime(self):
        data = self._read_sys_file('/proc/uptime')
        if not data: return "Up: 0d"
        
        total_seconds = float(data.split()[0])
        days = int(total_seconds // 86400)
        
        if days >= 1:
            return f"Up: {days}d"
        
        hours = int(total_seconds // 3600)
        minutes = int((total_seconds % 3600) // 60)
        return f"Up: {hours}h{minutes}m"

    def get_disk_space(self):
        try:
            st = os.statvfs(self.disk_path)
            free_bytes = st.f_bavail * st.f_frsize
            return f"DiskFree: {free_bytes / (1024**3):.1f}G"
        except FileNotFoundError:
            return "DiskFree: N/A"

    def get_memory(self):
        data = self._read_sys_file('/proc/meminfo').splitlines()
        mem = {}
        for line in data:
            if ':' in line:
                parts = line.split(':')
                mem[parts[0]] = int(parts[1].split()[0])
        
        total = mem.get('MemTotal', 1)
        available = mem.get('MemAvailable', 1)
        used = total - available
        
        swap_total = mem.get('SwapTotal', 1)
        swap_free = mem.get('SwapFree', 1)
        swap_used = swap_total - swap_free
        
        u_gb = used / (1024**2)
        t_gb = total / (1024**2)
        s_mb = int(swap_used / 1024)
        
        return f"RAM: {u_gb:.1f}/{t_gb:.1f}/{s_mb}M"

    def get_cpu(self):
        temp_data = self._read_sys_file(self.temp_path) if self.temp_path else ""
        temp_str = f"{int(temp_data.strip()) // 1000}°C" if temp_data else "N/A"

        stat_data = self._read_sys_file('/proc/stat')
        if not stat_data: return f"CPU: 0% {temp_str}"
        
        cpu_times = [float(i) for i in stat_data.splitlines()[0].split()[1:]]
        idle = cpu_times[3] + cpu_times[4] 
        total = sum(cpu_times)
        
        diff_idle = idle - self.prev_cpu_idle
        diff_total = total - self.prev_cpu_total
        usage = 100.0 * (1.0 - diff_idle / diff_total) if diff_total else 0.0
        
        self.prev_cpu_idle = idle
        self.prev_cpu_total = total
        
        return f"CPU: {int(usage)}% {temp_str}"

    def get_network(self):
        current_time = time.time()
        rx_bytes = self._read_sys_int(self.rx_path)
        tx_bytes = self._read_sys_int(self.tx_path)
        
        total_rx_mb = rx_bytes / (1024**2)
        total_tx_mb = tx_bytes / (1024**2)
        total_bw = total_rx_mb + total_tx_mb
        
        tot_str = f"{total_bw / 1024:.1f}GB" if total_bw >= 1024 else f"{int(total_bw)}MB"
        time_diff = current_time - self.prev_time
        
        if time_diff > 0:
            rx_speed = self._format_speed(((rx_bytes - self.prev_rx_bytes) * 8) / time_diff)
            tx_speed = self._format_speed(((tx_bytes - self.prev_tx_bytes) * 8) / time_diff)
        else:
            rx_speed, tx_speed = "0Kbps", "0Kbps"
            
        self.prev_time = current_time
        self.prev_rx_bytes = rx_bytes
        self.prev_tx_bytes = tx_bytes
        
        return f"Rx: {rx_speed} Tx: {tx_speed}  NetTot: {tot_str}"

    def run(self, interval=INTERVAL):
        self.get_cpu()
        self.get_network()
        time.sleep(interval)
        
        while True:
            bar_output = SEPARATOR.join([
                self.get_cpu(),
                self.get_memory(),
                self.get_disk_space(),
                self.get_network(),
                self.get_uptime()
            ])
            
            print(bar_output)
            sys.stdout.flush()
            time.sleep(interval)

if __name__ == "__main__":
    monitor = SystemMonitor()
    monitor.run()
