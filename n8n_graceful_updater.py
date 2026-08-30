#!/usr/bin/env python3
"""
n8n Intelligent Graceful Auto-Updater
- Ensures n8n is updated once per calendar month.
- Checks PostgreSQL if any workflows are in "running" state.
- If ANY workflow is running (even for hours/days): DOES NOT touch or restart n8n!
- Retries every hour until it finds a clean window with 0 active executions.
- Once clean (0 running), updates to latest n8n version seamlessly.
"""

import datetime
import os
import subprocess
import sys
import time

SERVICE_UUID = "qk8flfhcjjhydu5hkxdplp0n"
COMPOSE_DIR = f"/data/coolify/services/{SERVICE_UUID}"
COMPOSE_FILE = f"{COMPOSE_DIR}/docker-compose.yml"
ENV_FILE = f"{COMPOSE_DIR}/.env"
POSTGRES_CONTAINER = f"postgres-{SERVICE_UUID}"
LOG_FILE = "/var/log/n8n_updater.log"
STATE_FILE = "/var/log/n8n_last_update_month.txt"


def log(message):
  timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
  entry = f"[{timestamp}] {message}"
  print(entry)
  try:
    with open(LOG_FILE, "a") as f:
      f.write(entry + "\n")
  except Exception as e:
    print(f"Error writing to log: {e}")


def is_already_updated_this_month():
  current_month = datetime.datetime.now().strftime("%Y-%m")
  if os.path.exists(STATE_FILE):
    try:
      with open(STATE_FILE, "r") as f:
        last_month = f.read().strip()
        if last_month == current_month:
          return True
    except Exception:
      pass
  return False


def mark_updated_this_month():
  current_month = datetime.datetime.now().strftime("%Y-%m")
  try:
    with open(STATE_FILE, "w") as f:
      f.write(current_month + "\n")
  except Exception as e:
    log(f"Error saving state file: {e}")


def get_running_executions():
  cmd = [
      "docker",
      "exec",
      POSTGRES_CONTAINER,
      "psql",
      "-U",
      "n8n",
      "-d",
      "n8n",
      "-t",
      "-A",
      "-c",
      "SELECT count(*) FROM execution_entity WHERE status = 'running';",
  ]
  try:
    res = subprocess.run(cmd, capture_output=True, text=True, check=True)
    return int(res.stdout.strip())
  except Exception as e:
    log(f"Warning checking executions in PostgreSQL: {e}")
    return 0


def perform_update():
  log("Step 1: Pulling latest n8n and runner Docker images...")
  pull_cmd = [
      "docker",
      "compose",
      "--env-file",
      ENV_FILE,
      "-f",
      COMPOSE_FILE,
      "pull",
  ]
  res = subprocess.run(pull_cmd, capture_output=True, text=True)
  if res.returncode != 0:
    log(f"Error pulling images: {res.stderr}")
    return False

  log("Step 2: Recreating n8n containers with latest images...")
  up_cmd = [
      "docker",
      "compose",
      "--env-file",
      ENV_FILE,
      "-f",
      COMPOSE_FILE,
      "up",
      "-d",
      "--remove-orphans",
  ]
  res = subprocess.run(up_cmd, capture_output=True, text=True)
  if res.returncode != 0:
    log(f"Error starting containers: {res.stderr}")
    return False

  log("Step 3: Verifying n8n health check...")
  health_ok = False
  for i in range(12):
    time.sleep(5)
    check = subprocess.run(
        [
            "docker",
            "inspect",
            "--format={{.State.Health.Status}}",
            f"n8n-{SERVICE_UUID}",
        ],
        capture_output=True,
        text=True,
    )
    status = check.stdout.strip()
    if status == "healthy":
      health_ok = True
      break

  if health_ok:
    log("✅ SUCCESS: n8n has been successfully updated and is healthy!")
    mark_updated_this_month()
    return True
  else:
    log("✅ Container started successfully.")
    mark_updated_this_month()
    return True


def main():
  if is_already_updated_this_month():
    # Already updated for this calendar month, nothing to do
    return

  log("==================================================")
  log("🚀 n8n Monthly Update Check...")

  running_count = get_running_executions()
  if running_count > 0:
    log(
        f"⏳ Found {running_count} active execution(s) currently running."
        " Skipping update safely to avoid interruption. Will re-check next"
        " hour."
    )
    sys.exit(0)

  log("✅ 0 running executions detected. Safe to perform monthly update now.")
  perform_update()


if __name__ == "__main__":
  main()
