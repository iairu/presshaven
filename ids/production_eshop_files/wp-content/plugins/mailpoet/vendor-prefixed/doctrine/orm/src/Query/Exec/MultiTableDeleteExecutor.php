<?php
declare (strict_types=1);
namespace MailPoetVendor\Doctrine\ORM\Query\Exec;
if (!defined('ABSPATH')) exit;
use MailPoetVendor\Doctrine\DBAL\Connection;
use MailPoetVendor\Doctrine\DBAL\Connections\PrimaryReadReplicaConnection;
use MailPoetVendor\Doctrine\DBAL\Types\Type;
use MailPoetVendor\Doctrine\ORM\Query\AST;
use MailPoetVendor\Doctrine\ORM\Query\AST\DeleteStatement;
use MailPoetVendor\Doctrine\ORM\Query\SqlWalker;
use MailPoetVendor\Doctrine\ORM\Utility\PersisterHelper;
use Throwable;
use function array_merge;
use function array_reverse;
use function implode;
class MultiTableDeleteExecutor extends AbstractSqlExecutor
{
private $createTempTableSql;
private $dropTempTableSql;
private $insertSql;
public function __construct(AST\Node $AST, $sqlWalker)
{
parent::__construct();
$em = $sqlWalker->getEntityManager();
$conn = $em->getConnection();
$platform = $conn->getDatabasePlatform();
$quoteStrategy = $em->getConfiguration()->getQuoteStrategy();
if ($conn instanceof PrimaryReadReplicaConnection) {
$conn->ensureConnectedToPrimary();
}
$primaryClass = $em->getClassMetadata($AST->deleteClause->abstractSchemaName);
$primaryDqlAlias = $AST->deleteClause->aliasIdentificationVariable;
$rootClass = $em->getClassMetadata($primaryClass->rootEntityName);
$tempTable = $platform->getTemporaryTableName($rootClass->getTemporaryIdTableName());
$idColumnNames = $rootClass->getIdentifierColumnNames();
$idColumnList = implode(', ', $idColumnNames);
$sqlWalker->setSQLTableAlias($primaryClass->getTableName(), 't0', $primaryDqlAlias);
$this->insertSql = 'INSERT INTO ' . $tempTable . ' (' . $idColumnList . ')' . ' SELECT t0.' . implode(', t0.', $idColumnNames);
$rangeDecl = new AST\RangeVariableDeclaration($primaryClass->name, $primaryDqlAlias);
$fromClause = new AST\FromClause([new AST\IdentificationVariableDeclaration($rangeDecl, null, [])]);
$this->insertSql .= $sqlWalker->walkFromClause($fromClause);
if ($AST->whereClause) {
$this->insertSql .= $sqlWalker->walkWhereClause($AST->whereClause);
}
$idSubselect = 'SELECT ' . $idColumnList . ' FROM ' . $tempTable;
$classNames = array_merge($primaryClass->parentClasses, [$primaryClass->name], $primaryClass->subClasses);
foreach (array_reverse($classNames) as $className) {
$tableName = $quoteStrategy->getTableName($em->getClassMetadata($className), $platform);
$this->sqlStatements[] = 'DELETE FROM ' . $tableName . ' WHERE (' . $idColumnList . ') IN (' . $idSubselect . ')';
}
$columnDefinitions = [];
foreach ($idColumnNames as $idColumnName) {
$columnDefinitions[$idColumnName] = ['notnull' => \true, 'type' => Type::getType(PersisterHelper::getTypeOfColumn($idColumnName, $rootClass, $em))];
}
$this->createTempTableSql = $platform->getCreateTemporaryTableSnippetSQL() . ' ' . $tempTable . ' (' . $platform->getColumnDeclarationListSQL($columnDefinitions) . ', PRIMARY KEY(' . implode(',', $idColumnNames) . '))';
$this->dropTempTableSql = $platform->getDropTemporaryTableSQL($tempTable);
}
public function execute(Connection $conn, array $params, array $types)
{
$conn->executeStatement($this->createTempTableSql);
try {
$numDeleted = $conn->executeStatement($this->insertSql, $params, $types);
foreach ($this->sqlStatements as $sql) {
$conn->executeStatement($sql);
}
} catch (Throwable $exception) {
$conn->executeStatement($this->dropTempTableSql);
throw $exception;
}
$conn->executeStatement($this->dropTempTableSql);
return $numDeleted;
}
}
