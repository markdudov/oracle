#!/usr/bin/env python3
import json
import os
import sys

try:
    import oci
except ImportError:
    print("[ERROR] Инсталирайте библиотеките с: pip install -r requirements.txt")
    sys.exit(1)

CONFIG_FILE = "config.json"

def main():
    if not os.path.exists(CONFIG_FILE):
        print(f"[!] Файлът '{CONFIG_FILE}' все още не съществува. Моля копирайте 'config.example.json' като '{CONFIG_FILE}'.")
        return

    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        cfg = json.load(f)

    key_path = os.path.expanduser(cfg.get("key_file_path", ""))
    if not os.path.exists(key_path):
        print(f"[❌] Пътят до API частния ключ не съществува: {key_path}")
        return

    oci_cfg = {
        "user": cfg["user_ocid"],
        "key_file": key_path,
        "fingerprint": cfg["fingerprint"],
        "tenancy": cfg["tenancy_ocid"],
        "region": cfg.get("region", "eu-frankfurt-1")
    }

    try:
        print("[ℹ️] Проверка на връзката с Oracle Cloud Infrastructure API...")
        identity = oci.identity.IdentityClient(oci_cfg)
        user_info = identity.get_user(cfg["user_ocid"]).data
        print(f"[✅] Успешно свързване! Потребител: {user_info.name} ({user_info.description})")
        
        tenancy_id = cfg["tenancy_ocid"]
        print("\n[ℹ️] Извличане на подмрежи (Subnets) в Tenancy...")
        network = oci.core.VirtualNetworkClient(oci_cfg)
        subnets = network.list_subnets(compartment_id=tenancy_id).data
        for s in subnets:
            print(f"   -> Subnet: {s.display_name} | OCID: {s.id}")
            
        print("\n[ℹ️] Извличане на на налични изображения (Images) за ARM (A1.Flex)...")
        compute = oci.core.ComputeClient(oci_cfg)
        images = compute.list_images(
            compartment_id=tenancy_id,
            operating_system="Canonical Ubuntu",
            shape="VM.Standard.A1.Flex"
        ).data
        for img in images:
            print(f"   -> Image: {img.display_name} | OCID: {img.id}")

    except Exception as e:
        print(f"[❌] Грешка при тест на връзката: {e}")

if __name__ == "__main__":
    main()
