<?php
declare (strict_types=1);
namespace MailPoetVendor\Doctrine\DBAL\Platforms;
if (!defined('ABSPATH')) exit;
class PostgreSQL120Platform extends PostgreSQL100Platform
{
public function getDefaultColumnValueSQLSnippet(): string
{
return <<<'SQL'
    SELECT
        CASE
            WHEN a.attgenerated = 's' THEN NULL
            ELSE pg_get_expr(adbin, adrelid)
        END
     FROM pg_attrdef
     WHERE c.oid = pg_attrdef.adrelid
        AND pg_attrdef.adnum=a.attnum
SQL;
}
}
