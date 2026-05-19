#!/usr/bin/env python3
"""
Onboarding script for Inference Stack users.
Admin-only : creates an internal user in LiteLLM so they can self-serve
API keys via the Admin UI (/ui) or programmatically.
"""
import os
import sys
import argparse
import urllib.request
import json


def main():
    parser = argparse.ArgumentParser(description="Onboard a new user to Inference Stack")
    parser.add_argument("email", help="User email (used as user_id)")
    parser.add_argument("--role", default="internal_user", choices=["internal_user", "internal_user_viewer", "proxy_admin_viewer"], help="User role")
    parser.add_argument("--models", default="base-mind,bge-m3", help="Comma-separated allowed models")
    parser.add_argument("--budget", type=float, default=10.0, help="Monthly budget in USD. Use 0 for unlimited.")
    parser.add_argument("--proxy-url", default="http://127.0.0.1:4000", help="LiteLLM proxy URL")
    args = parser.parse_args()

    master_key = os.environ.get("LITELLM_MASTER_KEY")
    if not master_key:
        print("ERROR: LITELLM_MASTER_KEY not set in environment.", file=sys.stderr)
        sys.exit(1)

    budget = args.budget if args.budget > 0 else None
    payload = {
        "user_id": args.email,
        "user_email": args.email,
        "user_role": args.role,
        "models": args.models.split(","),
        "max_budget": budget,
    }

    req = urllib.request.Request(
        f"{args.proxy_url}/user/new",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {master_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read())
            print(f"User created successfully: {data.get('user_id')}")
            print(f"  Role: {args.role}")
            print(f"  Budget: ${args.budget}/month" if budget else "  Budget: unlimited")
            print(f"  Models: {args.models}")
            print(f"  Login URL: {args.proxy_url}/ui")
            print("  Password will be set on first login.")
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        print(f"ERROR {e.code}: {body}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
