#!/usr/bin/env bash

# This script generates a self-signed certificate for code signing.
# It creates a private key (codesign.key) and a certificate (codesign.crt).
# The private key should NOT be committed to version control.

set -e
cd "$(dirname "${BASH_SOURCE[0]}")" || exit 1

KEY_FILE="codesign.key"
CERT_FILE="codesign.crt"
DAYS_VALID=3650 # 10 years

if [ -f "$KEY_FILE" ] || [ -f "$CERT_FILE" ]; then
    echo "Error: Certificate files already exist in this directory."
    echo "Please remove '$KEY_FILE' and '$CERT_FILE' to generate new ones."
    exit 1
fi

echo ">>> Generating a 2048-bit RSA private key ($KEY_FILE)..."
openssl genpkey -algorithm RSA -out "$KEY_FILE" -pkeyopt rsa_keygen_bits:2048

echo ">>> Generating a self-signed certificate ($CERT_FILE)..."
openssl req -new -x509 -key "$KEY_FILE" -out "$CERT_FILE" -days "$DAYS_VALID" -subj "/O=indoctrinatedrecluse/CN=Owlcat Portrait Tool Development"

echo ""
echo "✅ Successfully generated '$KEY_FILE' and '$CERT_FILE'."
echo "IMPORTANT: Add '$KEY_FILE' to your .gitignore file. It should not be committed."