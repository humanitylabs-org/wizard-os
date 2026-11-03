#!/bin/bash
cd "$(dirname "$0")"
P=$PWD/profiles8-upg-dev
QUICK=1 QA_SOCKS_PORT=1081 timeout 280 node run8diag.cjs $PWD/profiles8-upg r8-upg-1081 store-get > ../runs8/30-upg-get-1081.log 2>&1; echo "30 $?"
QA_SOCKS_PORT=1082 timeout 840 node run8diag.cjs $P r8-upg-1082 store-get > ../runs8/31-upg-get-1082.log 2>&1; echo "31 $?"
QA_SOCKS_PORT=1082 timeout 560 node run8diag.cjs $P r8-upg-1082-rm store-remove > ../runs8/32-upg-remove-1082.log 2>&1; echo "32 $?"
LINK_COMMIT=1b30909c4976dc9ad19cd11a817fe51981fe39ac QA_SOCKS_PORT=1082 timeout 840 node run8diag.cjs $P r8-upg-link015 link > ../runs8/33-upg-link-015.log 2>&1; echo "33 $?"
EXPECT='Switch to this release' LINK_COMMIT=5aceb5de7be1bc62b1eb287363df5bf1e88a864b QA_SOCKS_PORT=1082 timeout 840 node run8diag.cjs $P r8-upg-link016 link > ../runs8/34-upg-link-016.log 2>&1; echo "34 $?"
QA_SOCKS_PORT=1082 timeout 560 node run8diag.cjs $P r8-upg-1082-rm016 store-remove > ../runs8/35-upg-remove-016.log 2>&1; echo "35 $?"
