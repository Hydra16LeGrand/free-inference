#!/bin/sh
# Copy nginx configs to a writable temp location, substitute ${DOMAIN},
# then launch nginx from the temp copy. This keeps the repo files untouched.

DOMAIN="${DOMAIN:-tondomaine.com}"

mkdir -p /tmp/nginx-conf

# Substitute ${DOMAIN} in all .conf files
for f in /etc/nginx/conf.d/*.conf; do
  if [ -f "$f" ]; then
    sed "s/\${DOMAIN}/${DOMAIN}/g" "$f" > "/tmp/nginx-conf/$(basename "$f")"
  fi
done

# Copy main nginx.conf and point include to the temp conf.d
cp /etc/nginx/nginx.conf /tmp/nginx.conf
sed -i 's|include /etc/nginx/conf.d/\*.conf|include /tmp/nginx-conf/*.conf|' /tmp/nginx.conf

exec nginx -c /tmp/nginx.conf -g 'daemon off;'
