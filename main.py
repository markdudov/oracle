#!/usr/bin/env python3
import json
import os
import sys
import time
import datetime
import requests

try:
    import oci
except ImportError:
    print("[ERROR] Опитайте да инсталирате библиотеките с: pip install -r requirements.txt")
    sys.exit(1)

CONFIG_FILE = "config.json"
SUCCESS_MARKER = "/tmp/vm_created"

def log(msg, level="INFO"):
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    prefix = {
        "INFO": "[ℹ️ INFO]",
        "SUCCESS": "[✅ SUCCESS]",
        "WARN": "[⚠️ WARN]",
        "ERROR": "[❌ ERROR]"
    }.get(level, "[LOG]")
    print(f"{timestamp} {prefix} {msg}", flush=True)

def mark_success():
    try:
        with open(SUCCESS_MARKER, "w") as f:
            f.write("CREATED")
    except Exception:
        pass

def load_config():
    if os.getenv("OCI_CONFIG_JSON"):
        cfg = json.loads(os.getenv("OCI_CONFIG_JSON"))
    elif os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            cfg = json.load(f)
    else:
        log(f"Файлът '{CONFIG_FILE}' не е намерен!", "ERROR")
        sys.exit(1)

    required = ["user_ocid", "tenancy_ocid", "fingerprint", "key_file_path", "subnet_ocid", "image_ocid", "ssh_public_key"]
    missing = [req for req in required if not cfg.get(req) or "СЛОЖЕТЕ_ТУК" in str(cfg[req])]
    
    if missing:
        log(f"Моля попълнете валидни стойности за следните полета в {CONFIG_FILE}: {', '.join(missing)}", "ERROR")
        sys.exit(1)
        
    return cfg

def send_notification(cfg, title, message):
    log(f"Изпращане на нотификация: {title} - {message}", "INFO")
    
    # Telegram Notification
    tg_token = cfg.get("telegram_bot_token")
    tg_chat = cfg.get("telegram_chat_id")
    if tg_token and tg_chat:
        try:
            url = f"https://api.telegram.org/bot{tg_token}/sendMessage"
            payload = {"chat_id": tg_chat, "text": f"🎉 {title}\n\n{message}"}
            requests.post(url, json=payload, timeout=10)
        except Exception as e:
            log(f"Грешка при изпращане на Telegram съобщение: {e}", "WARN")

    # Discord Webhook Notification
    discord_url = cfg.get("discord_webhook_url")
    if discord_url:
        try:
            payload = {"content": f"🎉 **{title}**\n{message}"}
            requests.post(discord_url, json=payload, timeout=10)
        except Exception as e:
            log(f"Грешка при изпращане на Discord съобщение: {e}", "WARN")

def get_oci_config(cfg):
    key_pem = os.getenv("OCI_API_KEY_PEM")
    if key_pem:
        key_path = "/tmp/oci_api_key.pem"
        with open(key_path, "w", encoding="utf-8") as f:
            f.write(key_pem.strip() + "\n")
        os.chmod(key_path, 0o600)
    else:
        key_path = os.path.expanduser(cfg["key_file_path"])
        if not os.path.exists(key_path):
            log(f"Файлът с частния API ключ не съществува на път: {key_path}", "ERROR")
            sys.exit(1)

    oci_cfg = {
        "user": cfg["user_ocid"],
        "key_file": key_path,
        "fingerprint": cfg["fingerprint"],
        "tenancy": cfg["tenancy_ocid"],
        "region": cfg.get("region", "eu-frankfurt-1")
    }
    oci.config.validate_config(oci_cfg)
    return oci_cfg

def check_existing_instance(compute_client, compartment_ocid, display_name):
    try:
        instances = compute_client.list_instances(compartment_ocid).data
        for inst in instances:
            if inst.display_name == display_name and inst.lifecycle_state in ["RUNNING", "PROVISIONING", "STARTING"]:
                return inst
    except Exception as e:
        log(f"Проверка за съществуваща машина: {e}", "WARN")
    return None

def get_availability_domains(identity_client, compartment_ocid):
    try:
        ads_response = identity_client.list_availability_domains(compartment_ocid)
        ads = [ad.name for ad in ads_response.data]
        if ads:
            return ads
    except Exception as e:
        log(f"Не успя да извлече ADs чрез API: {e}", "WARN")
    
    return [
        "gVig:EU-FRANKFURT-1-AD-1",
        "gVig:EU-FRANKFURT-1-AD-2",
        "gVig:EU-FRANKFURT-1-AD-3"
    ]

def try_launch_instance(compute_client, ad, cfg):
    compartment_ocid = cfg.get("compartment_ocid") or cfg["tenancy_ocid"]
    ocpus = float(cfg.get("ocpus", 4))
    memory_in_gbs = float(cfg.get("memory_in_gbs", 24))
    display_name = cfg.get("display_name", "oracle-arm-instance")
    boot_volume_size = int(cfg.get("boot_volume_size_in_gbs", 50))
    
    launch_details = oci.core.models.LaunchInstanceDetails(
        compartment_id=compartment_ocid,
        availability_domain=ad,
        display_name=display_name,
        shape="VM.Standard.A1.Flex",
        shape_config=oci.core.models.LaunchInstanceShapeConfigDetails(
            ocpus=ocpus,
            memory_in_gbs=memory_in_gbs
        ),
        source_details=oci.core.models.InstanceSourceViaImageDetails(
            image_id=cfg["image_ocid"],
            boot_volume_size_in_gbs=boot_volume_size
        ),
        create_vnic_details=oci.core.models.CreateVnicDetails(
            subnet_id=cfg["subnet_ocid"],
            assign_public_ip=True
        ),
        metadata={
            "ssh_authorized_keys": cfg["ssh_public_key"].strip()
        }
    )
    
    response = compute_client.launch_instance(launch_details)
    return response.data

def main():
    log("=== Стартиране на Oracle Free Tier Auto-Retry script ===", "INFO")
    cfg = load_config()
    oci_cfg = get_oci_config(cfg)
    
    identity_client = oci.identity.IdentityClient(oci_cfg)
    compute_client = oci.core.ComputeClient(oci_cfg)
    
    compartment_ocid = cfg.get("compartment_ocid") or cfg["tenancy_ocid"]
    display_name = cfg.get("display_name", "oracle-arm-instance")

    # Check if instance already exists
    existing = check_existing_instance(compute_client, compartment_ocid, display_name)
    if existing:
        log(f"🎉 Машината '{display_name}' вече съществува и е със статус {existing.lifecycle_state}! Прекратяване.", "SUCCESS")
        mark_success()
        sys.exit(0)
    
    ads = get_availability_domains(identity_client, compartment_ocid)
    log(f"Availability Domains ({oci_cfg['region']}): {', '.join(ads)}", "INFO")
    
    single_run = os.getenv("SINGLE_RUN") == "true" or os.getenv("GITHUB_ACTIONS") == "true"
    max_loops = 5 if single_run else sys.maxsize
    interval = int(cfg.get("retry_interval_seconds", 600))
    
    attempt = 0
    while attempt < max_loops:
        attempt += 1
        log(f"--- Опит #{attempt} ---", "INFO")
        
        for ad in ads:
            log(f"Опит за създаване на машина в AD: {ad}...", "INFO")
            try:
                created_instance = try_launch_instance(compute_client, ad, cfg)
                log(f"🎉 УСПЕХ! Машината беше създадена успешно в {ad}!", "SUCCESS")
                log(f"Instance ID: {created_instance.id}", "SUCCESS")
                mark_success()
                
                send_notification(
                    cfg,
                    "Oracle Cloud VM Created Successfully!",
                    f"Машината '{created_instance.display_name}' беше създадена в {ad}.\nInstance ID: {created_instance.id}"
                )
                sys.exit(0)
            except oci.exceptions.ServiceError as se:
                if se.status in [500, 429] or "capacity" in se.message.lower() or "outofcapacity" in se.code.lower():
                    log(f"Няма капацитет в {ad} ({se.code})", "WARN")
                elif se.status == 400 and "limit" in se.message.lower():
                    log(f"Достигнат лимит: {se.message}", "ERROR")
                    mark_success()
                    sys.exit(1)
                else:
                    log(f"Грешка OCI API ({ad}): {se.status} - {se.message}", "ERROR")
            except Exception as e:
                log(f"Грешка ({ad}): {e}", "ERROR")
        
        if attempt < max_loops:
            wait_time = 45 if single_run else interval
            log(f"Изчакване {wait_time} секунди преди следващ опит...", "INFO")
            time.sleep(wait_time)

    log("Завършен цикъл на опити за този екземпляр.", "INFO")

if __name__ == "__main__":
    main()
