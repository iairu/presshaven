# wordpress_hardened: the stock WordPress image with interim mitigations for
# PHP2Shell (CVE-2026-109618 / CVE-2026-109619, "Black October").
#
# Deliberately the SAME WordPress 6.8.3 / PHP 8.1.33 as before -- PHP 8.1 is
# end of life and gets no binary fix, and this image exists to show how the
# stack is protected while a vulnerable runtime stays in place. The base is
# pinned by digest so a re-tag upstream can't silently change what runs.
# Moving to a patched branch (-php8.3 >= 8.3.36, -php8.4 >= 8.4.27) is still
# the real fix; see docs-astro .../ai-defense/black-october.
#
# What changes (web SAPI only -- wp-cli and `php` in the container are not
# affected, everything is set from Apache with php_admin_*):
#   * php-black-october.conf  -- PHP settings that remove the trigger paths
#   * mpm-black-october.conf  -- one request per Apache child, so no request
#                                ever runs on a worker an earlier one touched
# The edge's body guard (reverse_proxy_enhanced/lua/body_guard_rules.lua)
# strips the request bodies these exploits need before they reach Apache.
FROM wordpress:6.8.3-php8.1@sha256:eeef49fcf96858412e393d73d7b2894610ade3af929da3975ae463584ff7ce46

COPY php-black-october.conf /etc/apache2/conf-available/php-black-october.conf
COPY mpm-black-october.conf /etc/apache2/conf-available/mpm-black-october.conf
COPY php-black-october.ini /usr/local/etc/php/conf.d/zz-black-october.ini
RUN a2enconf php-black-october mpm-black-october \
 && apache2ctl -t
