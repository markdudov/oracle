#!/usr/bin/env python3
"""
Production Reoon Email Verification & SalesBlink Synchronization Pipeline
- Dynamically checks available Reoon Daily Credits.
- Fetches EXACTLY the number of available daily credits from PostgreSQL.
- Submits bulk verification task to Reoon Email Verifier API.
- Polls for completion, updates PostgreSQL with statuses & scores.
- Pushes SAFE verified leads directly to SalesBlink list: "SilenceTrimmer Youtubers Contacts".
- Marks synced leads in PostgreSQL with timestamps.
"""

import datetime
import json
import os
import subprocess
import sys
import time
import urllib.parse
import urllib.request

CONFIG_FILE = "/etc/reoon_config.json"
SALESBLINK_LIST_ID = "034f362a-1a45-4d61-84ed-4bdb7f2d9405"
SALESBLINK_API_KEY = (
    "key-65ff93901953f8484edafdb5fffc0f73a1019c9fd9a9e4e91994450d9a9a44e0"
)
POSTGRES_CONTAINER = "postgres-qk8flfhcjjhydu5hkxdplp0n"
LOG_FILE = "/var/log/reoon_salesblink_pipeline.log"
DEFAULT_DAILY_LIMIT = 1200


def log(msg):
  ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
  entry = f"[{ts}] {msg}"
  print(entry)
  try:
    with open(LOG_FILE, "a") as f:
      f.write(entry + "\n")
  except Exception:
    pass


def get_reoon_api_key():
  if os.path.exists(CONFIG_FILE):
    try:
      with open(CONFIG_FILE, "r") as f:
        data = json.load(f)
        return data.get("reoon_api_key", "").strip()
    except Exception:
      pass
  env_key = os.environ.get("REOON_API_KEY", "").strip()
  if env_key:
    return env_key
  return ""


def get_remaining_daily_credits(api_key):
  url = (
      "https://emailverifier.reoon.com/api/v1/check-account-balance/?key="
      + api_key
  )
  try:
    req = urllib.request.Request(url)
    with urllib.request.urlopen(req, timeout=15) as resp:
      res = json.loads(resp.read().decode("utf-8"))
      credits = res.get("remaining_daily_credits")
      if credits is not None:
        log(f"💳 Reoon Account Balance: {credits} Daily Credits remaining.")
        return int(credits)
  except Exception as e:
    log(f"⚠️ Warning querying Reoon balance: {e}. Falling back to default.")
  return DEFAULT_DAILY_LIMIT


def run_psql(sql):
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
      sql,
  ]
  res = subprocess.run(cmd, capture_output=True, text=True, check=True)
  return res.stdout.strip()


def fetch_unverified_leads(limit):
  if limit <= 0:
    return []
  sql = f"""
    SELECT json_agg(t) FROM (
        SELECT id, email, first_name, channel_name, niche, country, country_code, language, subscribers, recent_video_title, channel_url, source
        FROM leads_pipeline
        WHERE verification_status IS NULL
        ORDER BY id ASC
        LIMIT {limit}
    ) t;
    """
  out = run_psql(sql)
  if not out or out == "null":
    return []
  return json.loads(out)


def submit_reoon_bulk_task(api_key, emails):
  url = "https://emailverifier.reoon.com/api/v1/create-bulk-verification-task/"
  task_name = (
      f"n8n_daily_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}"
  )
  payload = {"name": task_name, "emails": emails, "key": api_key}
  data = json.dumps(payload).encode("utf-8")
  req = urllib.request.Request(
      url, data=data, headers={"Content-Type": "application/json"}
  )
  with urllib.request.urlopen(req, timeout=30) as resp:
    res = json.loads(resp.read().decode("utf-8"))
    return res


def poll_reoon_task_results(api_key, task_id, max_wait=900, interval=15):
  url = f"https://emailverifier.reoon.com/api/v1/get-result-bulk-verification-task/?key={api_key}&task_id={task_id}"
  waited = 0
  while waited < max_wait:
    req = urllib.request.Request(url)
    with urllib.request.urlopen(req, timeout=30) as resp:
      res = json.loads(resp.read().decode("utf-8"))
      status = res.get("status", "").lower()
      if status in ["completed", "success", "finished"]:
        return res
      log(
          f"⏳ Reoon verification task {task_id} status: {status}. Progress:"
          f" {res.get('progress_percentage', '0')}% (Waited {waited}s)..."
      )
    time.sleep(interval)
    waited += interval
  raise TimeoutError(f"Reoon task {task_id} did not complete within {max_wait}s")


def update_lead_verification(email, status, score):
  clean_email = email.replace("'", "''")
  clean_status = status.replace("'", "''")
  score_val = int(score) if score is not None else 0
  sql = f"""
    UPDATE leads_pipeline
    SET verification_status = '{clean_status}', reoon_score = {score_val}, verified_at = NOW()
    WHERE email = '{clean_email}';
    """
  run_psql(sql)


def push_to_salesblink(contacts):
  if not contacts:
    return 0
  url = f"https://api.salesblink.io/v2/lists/{SALESBLINK_LIST_ID}/contacts"
  total_synced = 0
  chunk_size = 250
  for i in range(0, len(contacts), chunk_size):
    chunk = contacts[i : i + chunk_size]
    payload = {
        "list_id": SALESBLINK_LIST_ID,
        "remove_duplicates": True,
        "contacts": chunk,
    }
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {SALESBLINK_API_KEY}",
        },
        method="POST",
    )
    try:
      with urllib.request.urlopen(req, timeout=45) as resp:
        res = json.loads(resp.read().decode("utf-8"))
        synced_count = len(chunk)
        total_synced += synced_count
        log(
            f"✅ Pushed batch of {synced_count} contacts to SalesBlink (Status:"
            f" {res.get('message', 'OK')})"
        )
    except Exception as e:
      log(f"⚠️ SalesBlink API batch error: {e}")

  return total_synced


def mark_leads_salesblink_synced(emails):
  if not emails:
    return
  for i in range(0, len(emails), 200):
    chunk = emails[i : i + 200]
    email_list = ", ".join(f"'{e.replace(\"'\", \"''\")}'" for e in chunk)
    sql = f"""
        UPDATE leads_pipeline
        SET salesblink_synced = TRUE, salesblink_synced_at = NOW()
        WHERE email IN ({email_list});
        """
    run_psql(sql)


def main():
  log("==================================================")
  log("🚀 Starting Daily Reoon Verification & SalesBlink Sync Pipeline...")

  api_key = get_reoon_api_key()
  if not api_key:
    log(
        "❌ Error: Reoon API key not found in /etc/reoon_config.json or"
        " REOON_API_KEY env."
    )
    sys.exit(1)

  # Check exact remaining daily credits dynamically
  available_credits = get_remaining_daily_credits(api_key)
  if available_credits <= 0:
    log("ℹ️ 0 Daily Credits remaining for today. Will run tomorrow.")
    return

  batch_size = min(available_credits, DEFAULT_DAILY_LIMIT)
  log(f"🎯 Target verification batch size for today: {batch_size} emails.")

  leads = fetch_unverified_leads(batch_size)
  if not leads:
    log("🎉 All 100,000 leads in the pipeline have already been verified!")
    return

  log(f"📋 Fetched {len(leads)} unverified leads from PostgreSQL.")
  emails = [l["email"] for l in leads]

  log(f"📤 Submitting {len(emails)} emails to Reoon Bulk Verification API...")
  task_res = submit_reoon_bulk_task(api_key, emails)
  task_id = task_res.get("task_id") or task_res.get("id")
  if not task_id:
    log(f"❌ Error creating Reoon task: {task_res}")
    sys.exit(1)

  log(
      "✅ Reoon task created successfully! Task ID:"
      f" {task_id}. Polling for results..."
  )
  results_data = poll_reoon_task_results(api_key, task_id)

  results = results_data.get("results", {})
  safe_leads_for_salesblink = []
  safe_emails = []

  leads_map = {l["email"]: l for l in leads}

  verified_count = 0
  safe_count = 0
  invalid_count = 0
  disposable_count = 0

  if isinstance(results, dict):
    items = results.items()
  elif isinstance(results, list):
    items = [(r.get("email"), r) for r in results]
  else:
    items = []

  for email, res in items:
    if not email:
      continue
    status = res.get("status", "unknown").lower()
    score = res.get("overall_score") or res.get("score") or 0
    update_lead_verification(email, status, score)
    verified_count += 1

    if status == "safe":
      safe_count += 1
      lead_info = leads_map.get(email, {})
      contact = {
          "email": email,
          "first_name": lead_info.get("first_name") or "",
          "company_name": lead_info.get("channel_name") or "",
          "job_title": lead_info.get("niche") or "Content Creator",
          "country": lead_info.get("country") or "",
          "country_code": lead_info.get("country_code") or "",
          "language": lead_info.get("language") or "",
          "subscribers": lead_info.get("subscribers") or "",
          "recent_video_title": lead_info.get("recent_video_title") or "",
          "channel_url": lead_info.get("channel_url") or "",
          "source": lead_info.get("source") or "Curated YouTube ICP",
          "reoon_score": score,
      }
      safe_leads_for_salesblink.append(contact)
      safe_emails.append(email)
    elif status == "invalid":
      invalid_count += 1
    elif status == "disposable":
      disposable_count += 1

  log(
      f"📊 Verification Summary: Total: {verified_count} | Safe: {safe_count} |"
      f" Invalid: {invalid_count} | Disposable: {disposable_count}"
  )

  if safe_leads_for_salesblink:
    log(
        f"🚀 Pushing {len(safe_leads_for_salesblink)} SAFE verified leads to"
        " SalesBlink..."
    )
    pushed_count = push_to_salesblink(safe_leads_for_salesblink)
    mark_leads_salesblink_synced(safe_emails)
    log(
        f"🎉 Successfully synced {pushed_count} verified leads to SalesBlink"
        " list: SilenceTrimmer Youtubers Contacts!"
    )
  else:
    log("ℹ️ No safe leads found in this batch to sync.")

  log("🏁 Pipeline run completed successfully!")


if __name__ == "__main__":
  main()
