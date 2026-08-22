# 🚀 Oracle Cloud Always Free VM (Frankfurt Region)

Това репозиторий съдържа пълен комплект от инструменти, автоматизации и скриптове за създаване, поддръжка и защита на **Always Free ARM виртуална машина** в Oracle Cloud Infrastructure (OCI) в регион Франкфурт (`eu-frankfurt-1`).

---

## 🖥️ Спецификации на създадената машина

- **Име (Instance Name):** `oracle-arm-instance`
- **Процесори (OCPU):** `4.0 OCPU` (Ampere Altra ARM A1)
- **Оперативна памет (RAM):** `24.0 GB RAM`
- **Системен диск (NVMe/SSD):** `200.0 GB`
- **Статичен публичен IP адрес:** `130.162.229.179` *(Reserved Static IP)*
- **Операционна система:** Canonical Ubuntu 24.04 LTS (aarch64)

### 🔑 Връзка през SSH:
```bash
ssh -i ~/.ssh/id_ed25519_oracle ubuntu@130.162.229.179
```

---

## 🛡️ Anti-Idle Защита (Срещу изтриване от Oracle)

Според политиката на Oracle Cloud, безплатните машини подлежат на изтриване, ако в рамките на 7 дни натоварването им е под 20% (CPU/RAM). 

За да предпазите машината от изтриване, докато решите какви проекти да инсталирате на нея, използвайте **Anti-Idle услугата**, която поддържа ~5.5 GB RAM заети (24% от 24 GB) и лек фонов пулс на процесора.

---

### 📋 Вариант 1: Бързо инсталиране с 1 команда (Copy & Paste)

Свържете се към машината през SSH:
```bash
ssh -i ~/.ssh/id_ed25519_oracle ubuntu@130.162.229.179
```

И копирайте следния цял блок в терминала:

```bash
sudo bash -c 'cat << "EOF" > /opt/oracle_keepalive.py
#!/usr/bin/env python3
import time
import math

# Заема 5.5 GB RAM (24% от 24 GB)
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

### 📋 Вариант 2: Директно изпълнение от GitHub (1 ред)

Ако сте преинсталирали машината от нулата, изпълнете следния 1 ред в терминала на виртуалната машина:

```bash
curl -sSL https://raw.githubusercontent.com/markdudov/oracle/main/anti_idle_setup.sh | sudo bash
```

---

### 🔍 Полезни команди за управление:

- **Проверка на статуса на услугата:**
  ```bash
  sudo systemctl status oracle-keepalive.service
  ```

- **Проверка на заетата оперативна памет (RAM):**
  ```bash
  free -h
  ```

- **Спиране и премахване на защитата (когато качите реалните си проекти):**
  ```bash
  sudo systemctl disable --now oracle-keepalive.service
  ```

---

## 💽 Разпъване на диска до 200 GB (при преинсталация)

Ако някога преинсталирате Ubuntu и дискът показва 50 GB вместо 200 GB:

```bash
# 1. Пресканиране на диска от Linux ядрото
echo 1 | sudo tee /sys/class/block/sda/device/rescan

# 2. Разпъване на дяла и файловата система
sudo growpart /dev/sda 1
sudo resize2fs /dev/sda1

# 3. Проверка
df -h
```
