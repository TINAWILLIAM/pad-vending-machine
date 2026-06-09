#!/usr/bin/env python
"""
generate_qr.py – CLI tool to generate machine QR codes.

Usage:
    python scripts/generate_qr.py --machine-id <id> [--url <frontend-url>]
    python scripts/generate_qr.py --url <tunnel-url>            # generic QR
"""
import argparse
import sys
import os

# Allow running from repo root
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.utils.qr_generator import generate_machine_qr
from app.config import settings


def main():
    parser = argparse.ArgumentParser(description="Generate QR codes for vending machines")
    parser.add_argument("--machine-id", default="demo", help="Machine ID or code")
    parser.add_argument("--url", default=settings.FRONTEND_URL, help="Frontend base URL")
    parser.add_argument("--out", default="qr_codes", help="Output directory")
    args = parser.parse_args()

    path = generate_machine_qr(args.machine_id, args.url, args.out)
    print(f"✅ QR saved to: {path}")
    print(f"   Encodes: {args.url}?machine={args.machine_id}")


if __name__ == "__main__":
    main()
