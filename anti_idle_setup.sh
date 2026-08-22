#!/bin/bash
# Oracle Cloud Always Free Anti-Idle Service Setup Script
set -e

echo "=== Инсталиране на Oracle Always Free Anti-Idle Service ==="

cat << "EOF" > /opt/oracle_keepalive.py
#!/usr/bin/env python3
import time
import math

# Заема 5.5 GB RAM (23-24% от 24 GB)
MEMORY_GB = 5.5
size_bytes = int(MEMORY_GB * 1024 * 1024 * 1024)
print(f"[KeepAlive] Allocating {MEMORY_GB} GB RAM (24% of 24GB)...")
mem_buffer = bytearray(size_bytes)
for i in range(0, size_bytes, 4096 * 1024):
    mem_buffer[i] = 1
print("[KeepAlive] Memory allocated. Running light CPU pulse...")

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

echo "✅ Anti-Idle услугата е инсталирана и стартирана успешно!"
echo "Проверка на паметта:"
free -h
