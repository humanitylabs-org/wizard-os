#!/usr/bin/env python3
"""Release train: mint a WizardOS Builder GitHub App installation token (1h) and print it. Usage: builder-app-token PEM [APP_ID INSTALL_ID]"""
import sys, time, json, base64, urllib.request
from cryptography.hazmat.primitives import serialization, hashes
from cryptography.hazmat.primitives.asymmetric import padding
pem = open(sys.argv[1], 'rb').read(); app = sys.argv[2] if len(sys.argv) > 2 else '5723441'; inst = sys.argv[3] if len(sys.argv) > 3 else '181131281'
k = serialization.load_pem_private_key(pem, None)
b = lambda x: base64.urlsafe_b64encode(x).rstrip(b'=')
now = int(time.time()); h = b(b'{"alg":"RS256","typ":"JWT"}'); p = b(json.dumps({'iat': now - 60, 'exp': now + 540, 'iss': app}).encode())
jwt = (h + b'.' + p + b'.' + b(k.sign(h + b'.' + p, padding.PKCS1v15(), hashes.SHA256()))).decode()
r = urllib.request.Request(f'https://api.github.com/app/installations/{inst}/access_tokens', method='POST',
                           headers={'Authorization': 'Bearer ' + jwt, 'Accept': 'application/vnd.github+json', 'User-Agent': 'wizardos-builder'})
print(json.load(urllib.request.urlopen(r, timeout=30))['token'])
