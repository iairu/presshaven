# container-firewall: owns a WordPress container's network namespace and holds
# its iptables ruleset (see container-firewall.php). production_eshop and every
# honeypot pool join one of these with network_mode service:<firewall>, so the
# rules apply to them while they themselves get no NET_ADMIN and no iptables.
#   production.json / honeypot.json -- the default ruleset per FIREWALL_PROFILE,
#                                      used until the dashboard's Container
#                                      Firewall page saves one
FROM alpine:3.24.3

RUN apk add --no-cache iptables ip6tables php84-cli \
 && ln -s /usr/bin/php84 /usr/local/bin/php
COPY container-firewall.php /usr/local/bin/container-firewall
COPY production.json honeypot.json /usr/local/share/container-firewall/
RUN chmod 0755 /usr/local/bin/container-firewall \
 && mkdir -p /var/lib/container-firewall \
 && for p in production honeypot; do FIREWALL_PROFILE=$p container-firewall default > /dev/null; done

CMD ["container-firewall", "run"]
