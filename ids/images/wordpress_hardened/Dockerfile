# wordpress_hardened: the stock WordPress image plus the PHP2Shell
# (CVE-2026-109618 / CVE-2026-109619, "Black October") mitigations, kept as
# defence in depth on a patched runtime.
#
# Base: WordPress 7.1.3 on PHP 8.4.27, which carries the upstream fix for
# both CVEs. Pinned by digest so a re-tag upstream can't silently change what
# runs. Until 2026-10 this image deliberately stayed on the vulnerable PHP
# 8.1.33 to show how the stack holds up with an unpatched runtime; see
# docs-astro .../ai-defense/black-october.
#
# What changes (web SAPI only -- wp-cli and `php` in the container are not
# affected, everything is set from Apache with php_admin_*):
#   * php-black-october.conf  -- PHP settings that remove the trigger paths
#   * mpm-black-october.conf  -- one request per Apache child, so no request
#                                ever runs on a worker an earlier one touched
#   * healthprobe-log.conf    -- the edge's own health probes are not written
#                                to the access log (not a security setting)
#   * zz-production-hardening.conf -- (zz: loads after security.conf)
#                                sensitive-file, uploads-PHP and directory
#                                listing blocks; only active with
#                                -D PRODUCTION_HARDENING (production_eshop)
# The edge's body guard (reverse_proxy_enhanced/lua/body_guard_rules.lua)
# strips the request bodies these exploits need before they reach Apache.
FROM wordpress:7.1.3-php8.4-apache@sha256:edbfa4a140f7c5950435f5737538ad83d25af4661b74b990d7ec1eff3bec99a8

COPY php-black-october.conf /etc/apache2/conf-available/php-black-october.conf
COPY mpm-black-october.conf /etc/apache2/conf-available/mpm-black-october.conf
COPY php-black-october.ini /usr/local/etc/php/conf.d/zz-black-october.ini
COPY healthprobe-log.conf /etc/apache2/conf-available/healthprobe-log.conf
COPY zz-production-hardening.conf /etc/apache2/conf-available/zz-production-hardening.conf
RUN a2enconf php-black-october mpm-black-october healthprobe-log zz-production-hardening \
 && sed -i 's#^\(\s*CustomLog \${APACHE_LOG_DIR}/access.log combined\)$#\1 env=!healthprobe#' \
        /etc/apache2/sites-available/000-default.conf \
 && grep -q 'env=!healthprobe' /etc/apache2/sites-available/000-default.conf \
 && apache2ctl -t \
 && apache2ctl -t -D PRODUCTION_HARDENING
