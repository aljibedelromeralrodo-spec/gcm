#!/usr/bin/env python3
"""Test email connection directly"""
import sys
from pathlib import Path
from dotenv import load_dotenv

# Load .env BEFORE importing email_service
ROOT_DIR = Path('/app/backend')
load_dotenv(ROOT_DIR / '.env')

sys.path.insert(0, '/app/backend')
import email_service as mail

print("Testing email configuration...")
print(f"Configured: {mail.configured()}")
print(f"Number of accounts: {len(mail.ACCOUNTS)}")

for i, acc in enumerate(mail.ACCOUNTS):
    print(f"\nAccount {i+1}:")
    print(f"  User: {acc['user']}")
    print(f"  Role: {acc['rol']}")
    print(f"  Password length: {len(acc['pwd'])}")

print("\n" + "="*70)
print("Testing get_status()...")
try:
    status = mail.get_status()
    print(f"Status: {status}")
except Exception as e:
    print(f"ERROR: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "="*70)
print("Testing fetch_recent(5)...")
try:
    emails = mail.fetch_recent(5)
    print(f"Fetched {len(emails)} emails")
    if emails:
        print(f"First email: {emails[0]}")
except Exception as e:
    print(f"ERROR: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "="*70)
print("Testing email_stats()...")
try:
    stats = mail.email_stats()
    print(f"Stats: {stats}")
except Exception as e:
    print(f"ERROR: {e}")
    import traceback
    traceback.print_exc()
