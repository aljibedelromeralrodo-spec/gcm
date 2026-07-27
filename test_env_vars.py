#!/usr/bin/env python3
"""Debug environment variables"""
import os
from pathlib import Path
from dotenv import load_dotenv

ROOT_DIR = Path('/app/backend')
env_file = ROOT_DIR / '.env'

print(f"Checking .env file: {env_file}")
print(f"File exists: {env_file.exists()}")

if env_file.exists():
    print(f"\n.env file contents:")
    with open(env_file) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#'):
                # Mask passwords
                if 'PASSWORD' in line:
                    key = line.split('=')[0]
                    print(f"{key}=***MASKED***")
                else:
                    print(line)

print("\n" + "="*70)
print("Loading .env file...")
load_dotenv(env_file)

print("\nEnvironment variables after load_dotenv:")
env_vars = ['MAIL_IMAP_HOST', 'MAIL_SMTP_HOST', 'MAIL_SMTP_PORT', 
            'MAIL_USER', 'MAIL_APP_PASSWORD', 'MAIL_FROM_NAME',
            'MAIL2_USER', 'MAIL2_APP_PASSWORD']

for var in env_vars:
    val = os.environ.get(var, '')
    if 'PASSWORD' in var:
        print(f"{var}: {'***SET***' if val else '***NOT SET***'} (length: {len(val)})")
    else:
        print(f"{var}: {val if val else '***NOT SET***'}")
