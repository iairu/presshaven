<?php
namespace MailPoetVendor\Doctrine\DBAL\Platforms;
if (!defined('ABSPATH')) exit;
use MailPoetVendor\Doctrine\DBAL\SQL\Builder\SelectSQLBuilder;
use function implode;
class MariaDb1010Platform extends MariaDb1060Platform
{
public function createSelectSQLBuilder(): SelectSQLBuilder
{
return AbstractPlatform::createSelectSQLBuilder();
}
public function fetchTableOptionsByTable(bool $includeTableName): string
{
$sql = <<<'SQL'
    SELECT t.TABLE_NAME,
           t.ENGINE,
           t.AUTO_INCREMENT,
           t.TABLE_COMMENT,
           t.CREATE_OPTIONS,
           t.TABLE_COLLATION,
           ccsa.CHARACTER_SET_NAME
      FROM information_schema.TABLES t
        INNER JOIN information_schema.COLLATION_CHARACTER_SET_APPLICABILITY ccsa
          ON ccsa.FULL_COLLATION_NAME = t.TABLE_COLLATION
SQL;
$conditions = ['t.TABLE_SCHEMA = ?'];
if ($includeTableName) {
$conditions[] = 't.TABLE_NAME = ?';
}
$conditions[] = "t.TABLE_TYPE = 'BASE TABLE'";
return $sql . ' WHERE ' . implode(' AND ', $conditions);
}
}
