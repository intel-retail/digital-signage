#!/bin/sh
#
# Apache v2 license
# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
#
# Renders nginx.conf and makes sure a TLS certificate exists in $SSL_DIR.
# $SSL_DIR is a host bind mount (configs/nginx/certs), so the identity
# survives restarts, reboots and `make up`. Invoked with `sh`, so stay POSIX.

SSL_DIR="/opt/nginx/certs"
CERT="$SSL_DIR/cert.pem"
KEY="$SSL_DIR/key.pem"
# Written only for certificates this script generated; holds their SAN list.
MARKER="$SSL_DIR/.generated-san"

KEY_LENGTH=3072
DAYS=365
SHA_ALGO="sha384"

# /etc/nginx is tmpfs, so the config must be rendered on every start.
envsubst '\$MEDIAMTX_SERVER \$WHIP_SERVER_PORT\' < /tmp/default.conf.template > /etc/nginx/nginx.conf

mkdir -p "$SSL_DIR"

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

generate_cert() {
    echo "Generating self-signed TLS certificate for nginx ($1)."
    echo "Clients that pinned the previous certificate must fetch the new one (GET /cert.pem)."
    rm -f "$CERT" "$KEY" "$MARKER"
    openssl req -x509 -nodes -days ${DAYS} -${SHA_ALGO} -newkey rsa:${KEY_LENGTH} \
        -keyout "$KEY" -out "$CERT" -subj "/CN=localhost" -addext "subjectAltName=$SAN" || exit 1
    printf '%s\n' "$SAN" > "$MARKER"
    chmod 600 "$KEY"
    chmod 644 "$CERT"
}

if [ -f "$CERT" ] && [ -f "$KEY" ]; then
    if [ ! -f "$MARKER" ]; then
        echo "Using operator-provided TLS certificate from $SSL_DIR."
    elif ! openssl x509 -in "$CERT" -noout -checkend 0 >/dev/null 2>&1; then
        generate_cert "previous certificate expired"
    elif [ "$(cat "$MARKER")" != "$SAN" ]; then
        generate_cert "SAN list changed, HOST_IP is now '${HOST_IP:-unset}'"
    else
        echo "Reusing existing self-signed TLS certificate from $SSL_DIR."
    fi
else
    generate_cert "no certificate present"
fi