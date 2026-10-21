#!/bin/bash
#
# Apache v2 license
# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
#

# Set working directory for SSL certificates
SSL_DIR="/opt/nginx/certs"
mkdir -p "$SSL_DIR"

# Set default values for SSL parameters if not provided
KEY_LENGTH=3072
DAYS=365
SHA_ALGO="sha384"

echo "Generating SSL certificates for Nginx..."
if [ -d $SSL_DIR ]; then rm -rf $SSL_DIR/*; fi

envsubst '\$MEDIAMTX_SERVER \$WHIP_SERVER_PORT\' < /tmp/default.conf.template > /etc/nginx/nginx.conf 

# SAN list so clients other than literal "localhost" (e.g. host.docker.internal
# from a sibling container, or the box's real IP from an external agent) can
# verify this self-signed cert instead of failing hostname verification.
SAN="DNS:localhost,IP:127.0.0.1,DNS:host.docker.internal"
if [ -n "$HOST_IP" ] && [ "$HOST_IP" != "localhost" ]; then
    if echo "$HOST_IP" | grep -qE '^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$'; then
        SAN="$SAN,IP:$HOST_IP"
    else
        SAN="$SAN,DNS:$HOST_IP"
    fi
fi

openssl req -x509 -nodes -days ${DAYS} -${SHA_ALGO} -newkey rsa:${KEY_LENGTH} -keyout $SSL_DIR/key.pem -out $SSL_DIR/cert.pem -subj "/CN=localhost" -addext "subjectAltName=$SAN"
chmod 640 $SSL_DIR/key.pem $SSL_DIR/cert.pem