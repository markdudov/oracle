# Oracle Cloud Always Free VM Auto-Retry Script (Frankfurt Region)

Този проект представлява автоматизиран скрипт на Python, който на всеки 10 минути се опитва да създаде виртуална машина в Oracle Cloud Infrastructure (OCI) в регион Франкфурт (`eu-frankfurt-1`).

Тъй като в безплатния ресурс **Always Free (Ampere ARM A1.Flex: 4 OCPU, 24 GB RAM)** често няма свободен капацитет (`Out of host capacity`), скриптът ротира през 3-те Availability Domains (AD-1, AD-2, AD-3) и прави автоматични опити, докато успее да създаде виртуалната машина.

---

## 🛠️ Бърза настройка (Стъпка по стъпка)

### Стъпка 1: Генериране на API Key в Oracle Cloud Console
Тъй като сте логнати в Chrome във вашия Oracle акаунт:
1. Отидете на профила си горе вдясно (иконката на човече) -> **User settings**.
2. Вляво изберете **API Keys** (под Resources).
3. Натиснете **Add API Key**.
4. Изберете **Generate API Key Pair** и свалете частния ключ (**Download Private Key**) – той се казва подобно на `oracleidentitycloudservice_...pem`.
5. Запазете го в папката `~/.oci/` (създайте я ако я няма):
   ```bash
   mkdir -p ~/.oci
   mv ~/Downloads/*.pem ~/.oci/oci_api_key.pem
   chmod 600 ~/.oci/oci_api_key.pem
   ```
6. Натиснете **Add** в конзолата на Oracle. Ще се покаже прозорец **Configuration File Preview**.
7. Копирайте оттам следните данни:
   - `user` (User OCID)
   - `fingerprint`
   - `tenancy` (Tenancy OCID)

---

### Стъпка 2: Вземане на Subnet & Image OCID (от вашия Stack)
Тъй като вече сте създали **Stack** в Oracle Cloud:
1. Влезте в **Resource Manager** -> **Stacks** в Oracle Console.
2. Кликнете върху създадения от вас Stack.
3. От падащото меню или **Terraform Variables / Outputs** вижте:
   - **Subnet OCID** (`ocid1.subnet.oc1.eu-frankfurt-1...`)
   - **Image OCID** (напр. Canonical Ubuntu 24.04/22.04 ARM)
   - **SSH Public Key** (вашият публичен SSH ключ, започващ с `ssh-rsa ...` или `ssh-ed25519 ...`)

---

### Стъпка 3: Създаване на `config.json`
Копирайте примерния файл:
```bash
cp config.example.json config.json
```

Отворете `config.json` и нанесете вашите стойности:
```json
{
  "user_ocid": "ocid1.user.oc1..вашия_user_ocid",
  "tenancy_ocid": "ocid1.tenancy.oc1..вашия_tenancy_ocid",
  "fingerprint": "xx:xx:xx:xx:xx:xx:xx:xx:xx:xx:xx:xx:xx:xx:xx:xx",
  "key_file_path": "~/.oci/oci_api_key.pem",
  "region": "eu-frankfurt-1",
  "compartment_ocid": "ocid1.tenancy.oc1..вашия_tenancy_ocid",
  "subnet_ocid": "ocid1.subnet.oc1.eu-frankfurt-1..вашия_subnet_ocid",
  "image_ocid": "ocid1.image.oc1.eu-frankfurt-1..вашия_image_ocid",
  "ssh_public_key": "ssh-rsa AAAAB3NzaC1yc2EAAA...",
  "ocpus": 4,
  "memory_in_gbs": 24,
  "display_name": "oracle-arm-instance",
  "boot_volume_size_in_gbs": 50,
  "retry_interval_seconds": 600,
  "telegram_bot_token": "",
  "telegram_chat_id": "",
  "discord_webhook_url": ""
}
```

---

### Стъпка 4: Инсталиране на зависимостите и Стартиране

1. Създайте виртуална среда и инсталирайте необходимите библиотеки:
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```

2. (Опционално) Тествайте връзката:
   ```bash
   python3 helper_setup.py
   ```

3. Стартирайте авто-опитите:
   ```bash
   python3 main.py
   ```

 За да работи скриптът във фонов режим дори когато затворите терминала:
```bash
nohup python3 main.py > oracle.log 2>&1 &
```
Можете да следите логовете с:
```bash
tail -f oracle.log
```

---

## 🔔 Известяване при успех
Можете да добавите Discord Webhook URL или Telegram Bot Token + Chat ID в `config.json`. Когато скриптът успешно създаде машината, той незабавно ще ви изпрати известие с детайли за машината и ще приключи работа.
