# 🚀 Oracle Cloud Always Free VM Instance (Frankfurt Region)

Complete toolkit, automation scripts, and management guides for creating, maintaining, and protecting an **Always Free ARM Virtual Machine** (`VM.Standard.A1.Flex`) on Oracle Cloud Infrastructure (OCI) in the Frankfurt region (`eu-frankfurt-1`).

---

## 🖥️ Server Specifications

| Parameter | Value |
| :--- | :--- |
| **Instance Name** | `oracle-arm-instance` |
| **Status** | 🟢 `RUNNING` |
| **Region & AD** | Frankfurt (`YsKy:EU-FRANKFURT-1-AD-3`) |
| **Processors (OCPU)** | **4.0 OCPU** (Ampere Altra ARM A1) |
| **Memory (RAM)** | **24.0 GB RAM** |
| **Storage (NVMe/SSD)** | **200.0 GB** |
| **Public IP Address** | 🔒 `<YOUR_RESERVED_STATIC_IP>` |
| **Operating System** | Canonical Ubuntu 24.04 LTS (`aarch64`) |

### 🔑 SSH Connection
Connect securely to your server from your terminal:
```bash
ssh -i ~/.ssh/id_ed25519_oracle ubuntu@<YOUR_SERVER_IP>
```

---

## 🛡️ Anti-Idle Protection (Preventing Oracle Reclaim)

According to Oracle Cloud's Always Free policy, instances are considered idle and eligible for reclamation if CPU, RAM, or network utilization stays below **20%** over a consecutive 7-day period.

To keep your machine active while you decide what projects to deploy, use the **Anti-Idle Keep-Alive Service**. It maintains **~5.5 GB RAM (~24% of 24 GB)** and a light continuous CPU pulse without overheating the server.

---

### 📋 Option 1: Quick Install (Copy & Paste 1 Command)

Connect to your instance via SSH:
```bash
ssh -i ~/.ssh/id_ed25519_oracle ubuntu@<YOUR_SERVER_IP>
```

Paste this entire block into your terminal:

```bash
sudo bash -c 'cat << "EOF" > /opt/oracle_keepalive.py
#!/usr/bin/env python3
import time
import math

# Allocate 5.5 GB RAM (24% of 24 GB)
MEMORY_GB = 5.5
size_bytes = int(MEMORY_GB * 1024 * 1024 * 1024)
mem_buffer = bytearray(size_bytes)
for i in range(0, size_bytes, 4096 * 1024):
    mem_buffer[i] = 1

while True:
    start_time = time.time()
    while time.time() - start_time < 0.22:
        _ = math.sqrt(123456789.0)
    time.sleep(0.78)
EOF
chmod +x /opt/oracle_keepalive.py

cat << "EOF" > /etc/systemd/system/oracle-keepalive.service
[Unit]
Description=Oracle Always Free Anti-Idle Keep Alive Service
After=network.target

[Service]
Type=simple
User=root
ExecStart=/usr/bin/python3 /opt/oracle_keepalive.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable --now oracle-keepalive.service
'
```

---

### 📋 Option 2: 1-Line Remote Execution via GitHub

If you ever reinstall your server from scratch, simply run this one-liner in your terminal:

```bash
curl -sSL https://raw.githubusercontent.com/markdudov/oracle/main/anti_idle_setup.sh | sudo bash
```

---

### 🔍 Useful Management Commands

- **Check Service Status:**
  ```bash
  sudo systemctl status oracle-keepalive.service
  ```

- **Verify Memory Allocation:**
  ```bash
  free -h
  ```

- **Stop / Disable Protection (when deploying your actual apps):**
  ```bash
  sudo systemctl disable --now oracle-keepalive.service
  ```

---

## 💽 Disk Expansion to 200 GB (If Reinstalled)

If you ever reinstall Ubuntu and the partition shows 50 GB instead of 200 GB, run:

```bash
# 1. Trigger kernel disk rescan
echo 1 | sudo tee /sys/class/block/sda/device/rescan

# 2. Expand partition and filesystem
sudo growpart /dev/sda 1
sudo resize2fs /dev/sda1

# 3. Verify expanded storage
df -h
```
