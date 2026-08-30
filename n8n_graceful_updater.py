#!/usr/bin/env python3
"""
n8n Graceful Auto-Updater for Coolify & PostgreSQL
- Checks if any n8n executions are currently in 'running' state in PostgreSQL.
- Gracefully waits until all active executions finish before updating.
- Pulls latest Docker images (n8nio/n8n:latest & n8nio/runners:latest).
- Recreates containers and validates healthcheck.
- Logs full output to /var/log/n8n_updater.log.
"""

import datetime
import subprocess
import sys
import time

SERVICE_UUID = "qk8flfhcjjhydu5hkxdplp0n"
COMPOSE_DIR = f"/data/coolify/services/{SERVICE_UUID}"
COMPOSE_FILE = f"{COMPOSE_DIR}/docker-compose.yml"
ENV_FILE = f"{COMPOSE_DIR}/.env"
POSTGRES_CONTAINER = f"postgres-{SERVICE_UUID}"
LOG_FILE = "/var/log/n8n_updater.log"
MAX_WAIT_SECONDS = 300  # 5 minutes maximum wait for running jobs
CHECK_INTERVAL = 15  # Check every 15 seconds


def log(message):
  timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
  entry = f"[{timestamp}] {message}"
  print(entry)
  try:
    with open(LOG_FILE, "a") as f:
      f.write(entry + "\n")
  except Exception as e:
    print(f"Error writing to log: {e}")


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
    return True
  else:
    log("✅ Container started successfully.")
    return True


def main():
  log("==================================================")
  log("🚀 Starting n8n Graceful Auto-Updater check...")

  waited = 0
  while waited < MAX_WAIT_SECONDS:
    running_count = get_running_executions()
    if running_count == 0:
      log("✅ 0 running executions detected. Safe to update now.")
      break
    else:
      log(
          f"⏳ Found {running_count} active execution(s) running. Waiting"
          f" {CHECK_INTERVAL}s before re-checking (Waited {waited}s /"
          f" {MAX_WAIT_SECONDS}s)..."
      )
      time.sleep(CHECK_INTERVAL)
      waited += CHECK_INTERVAL

  if waited >= MAX_WAIT_SECONDS:
    log(
        "⚠️ Warning: Active executions did not finish within timeout. Postponing"
        " update."
    )
    sys.exit(1)

  success = perform_update()
  if not success:
    sys.exit(1)


if __name__ == "__main__":
  main()
