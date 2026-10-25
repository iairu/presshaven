<?php
declare (strict_types=1);
namespace MailPoetVendor\Doctrine\ORM\Tools\Pagination;
if (!defined('ABSPATH')) exit;
use MailPoetVendor\Doctrine\DBAL\Platforms\AbstractPlatform;
use MailPoetVendor\Doctrine\DBAL\Platforms\DB2Platform;
use MailPoetVendor\Doctrine\DBAL\Platforms\OraclePlatform;
use MailPoetVendor\Doctrine\DBAL\Platforms\PostgreSQLPlatform;
use MailPoetVendor\Doctrine\DBAL\Platforms\SQLAnywherePlatform;
use MailPoetVendor\Doctrine\DBAL\Platforms\SQLServerPlatform;
use MailPoetVendor\Doctrine\ORM\EntityManagerInterface;
use MailPoetVendor\Doctrine\ORM\Mapping\QuoteStrategy;
use MailPoetVendor\Doctrine\ORM\OptimisticLockException;
use MailPoetVendor\Doctrine\ORM\Query;
use MailPoetVendor\Doctrine\ORM\Query\AST\DeleteStatement;
use MailPoetVendor\Doctrine\ORM\Query\AST\OrderByClause;
use MailPoetVendor\Doctrine\ORM\Query\AST\PathExpression;
use MailPoetVendor\Doctrine\ORM\Query\AST\SelectExpression;
use MailPoetVendor\Doctrine\ORM\Query\AST\SelectStatement;
use MailPoetVendor\Doctrine\ORM\Query\AST\UpdateStatement;
use MailPoetVendor\Doctrine\ORM\Query\Exec\SingleSelectSqlFinalizer;
use MailPoetVendor\Doctrine\ORM\Query\Exec\SqlFinalizer;
use MailPoetVendor\Doctrine\ORM\Query\Parser;
use MailPoetVendor\Doctrine\ORM\Query\ParserResult;
use MailPoetVendor\Doctrine\ORM\Query\QueryException;
use MailPoetVendor\Doctrine\ORM\Query\ResultSetMapping;
use MailPoetVendor\Doctrine\ORM\Query\SqlOutputWalker;
use LogicException;
use RuntimeException;
use function array_diff;
use function array_keys;
use function assert;
use function count;
use function implode;
use function in_array;
use function is_string;
use function method_exists;
use function preg_replace;
use function reset;
use function sprintf;
use function strrpos;
use function substr;
class LimitSubqueryOutputWalker extends SqlOutputWalker
{
private const ORDER_BY_PATH_EXPRESSION = '/(?<![a-z0-9_])%s\.%s(?![a-z0-9_])/i';
private $platform;
private $rsm;
private $firstResult;
private $maxResults;
private $em;
private $quoteStrategy;
private $orderByPathExpressions = [];
private $inSubSelect = \false;
public function __construct($query, $parserResult, array $queryComponents)
{
$this->platform = $query->getEntityManager()->getConnection()->getDatabasePlatform();
$this->rsm = $parserResult->getResultSetMapping();
$cloneQuery = clone $query;
$cloneQuery->setParameters(clone $query->getParameters());
$cloneQuery->setCacheable(\false);
foreach ($query->getHints() as $name => $value) {
$cloneQuery->setHint($name, $value);
}
$this->firstResult = $cloneQuery->getFirstResult();
$this->maxResults = $cloneQuery->getMaxResults();
$cloneQuery->setFirstResult(0)->setMaxResults(null);
$this->em = $cloneQuery->getEntityManager();
$this->quoteStrategy = $this->em->getConfiguration()->getQuoteStrategy();
parent::__construct($cloneQuery, $parserResult, $queryComponents);
}
private function platformSupportsRowNumber(): bool
{
return $this->platform instanceof PostgreSQLPlatform || $this->platform instanceof SQLServerPlatform || $this->platform instanceof OraclePlatform || $this->platform instanceof SQLAnywherePlatform || $this->platform instanceof DB2Platform || method_exists($this->platform, 'supportsRowNumberFunction') && $this->platform->supportsRowNumberFunction();
}
private function rebuildOrderByForRowNumber(SelectStatement $AST): void
{
$orderByClause = $AST->orderByClause;
$selectAliasToExpressionMap = [];
foreach ($AST->selectClause->selectExpressions as $selectExpression) {
if ($selectExpression->fieldIdentificationVariable !== null) {
$selectAliasToExpressionMap[$selectExpression->fieldIdentificationVariable] = $selectExpression->expression;
}
}
foreach ($orderByClause->orderByItems as $orderByItem) {
if (is_string($orderByItem->expression) && isset($selectAliasToExpressionMap[$orderByItem->expression])) {
$orderByItem->expression = $selectAliasToExpressionMap[$orderByItem->expression];
}
}
$func = new RowNumberOverFunction('dctrn_rownum');
$func->orderByClause = $AST->orderByClause;
$AST->selectClause->selectExpressions[] = new SelectExpression($func, 'dctrn_rownum', \true);
$AST->orderByClause = null;
}
public function walkSelectStatement(SelectStatement $AST)
{
$sqlFinalizer = $this->getFinalizer($AST);
$query = $this->getQuery();
$abstractSqlExecutor = $sqlFinalizer->createExecutor($query);
return $abstractSqlExecutor->getSqlStatements();
}
public function getFinalizer($AST): SqlFinalizer
{
if (!$AST instanceof SelectStatement) {
throw new LogicException(self::class . ' is to be used on SelectStatements only');
}
if ($this->platformSupportsRowNumber()) {
$sql = $this->createSqlWithRowNumber($AST);
} else {
$sql = $this->createSqlWithoutRowNumber($AST);
}
return new SingleSelectSqlFinalizer($sql);
}
public function walkSelectStatementWithRowNumber(SelectStatement $AST)
{
return $this->platform->modifyLimitQuery($this->createSqlWithRowNumber($AST), $this->maxResults, $this->firstResult);
}
private function createSqlWithRowNumber(SelectStatement $AST): string
{
$hasOrderBy = \false;
$outerOrderBy = ' ORDER BY dctrn_minrownum ASC';
$orderGroupBy = '';
if ($AST->orderByClause instanceof OrderByClause) {
$hasOrderBy = \true;
$this->rebuildOrderByForRowNumber($AST);
}
$innerSql = $this->getInnerSQL($AST);
$sqlIdentifier = $this->getSQLIdentifier($AST);
if ($hasOrderBy) {
$orderGroupBy = ' GROUP BY ' . implode(', ', $sqlIdentifier);
$sqlIdentifier[] = 'MIN(' . $this->walkResultVariable('dctrn_rownum') . ') AS dctrn_minrownum';
}
$sql = sprintf('SELECT DISTINCT %s FROM (%s) dctrn_result', implode(', ', $sqlIdentifier), $innerSql);
if ($hasOrderBy) {
$sql .= $orderGroupBy . $outerOrderBy;
}
foreach ($sqlIdentifier as $property => $alias) {
$this->rsm->addScalarResult($alias, $property);
}
return $sql;
}
public function walkSelectStatementWithoutRowNumber(SelectStatement $AST, $addMissingItemsFromOrderByToSelect = \true)
{
return $this->platform->modifyLimitQuery($this->createSqlWithoutRowNumber($AST, $addMissingItemsFromOrderByToSelect), $this->maxResults, $this->firstResult);
}
private function createSqlWithoutRowNumber(SelectStatement $AST, bool $addMissingItemsFromOrderByToSelect = \true): string
{
if ($AST->orderByClause instanceof OrderByClause && $addMissingItemsFromOrderByToSelect) {
$this->addMissingItemsFromOrderByToSelect($AST);
}
$orderByClause = $AST->orderByClause;
$AST->orderByClause = null;
$innerSql = $this->getInnerSQL($AST);
$sqlIdentifier = $this->getSQLIdentifier($AST);
$sql = sprintf('SELECT DISTINCT %s FROM (%s) dctrn_result', implode(', ', $sqlIdentifier), $innerSql);
$sql = $this->preserveSqlOrdering($sqlIdentifier, $innerSql, $sql, $orderByClause);
foreach ($sqlIdentifier as $property => $alias) {
$this->rsm->addScalarResult($alias, $property);
}
$AST->orderByClause = $orderByClause;
return $sql;
}
private function addMissingItemsFromOrderByToSelect(SelectStatement $AST): void
{
$this->orderByPathExpressions = [];
$walker = clone $this;
$walker->walkSelectStatementWithoutRowNumber($AST, \false);
$orderByPathExpressions = $walker->getOrderByPathExpressions();
$selects = [];
foreach ($orderByPathExpressions as $pathExpression) {
assert($pathExpression->field !== null);
$idVar = $pathExpression->identificationVariable;
$field = $pathExpression->field;
if (!isset($selects[$idVar])) {
$selects[$idVar] = [];
}
$selects[$idVar][$field] = \true;
}
foreach ($AST->selectClause->selectExpressions as $selectExpression) {
if ($selectExpression instanceof SelectExpression) {
$idVar = $selectExpression->expression;
if (!is_string($idVar)) {
continue;
}
$field = $selectExpression->fieldIdentificationVariable;
if ($field === null) {
unset($selects[$idVar]);
} else {
unset($selects[$idVar][$field]);
}
}
}
foreach ($selects as $idVar => $fields) {
$AST->selectClause->selectExpressions[] = new SelectExpression($idVar, null, \true);
}
}
private function preserveSqlOrdering(array $sqlIdentifier, string $innerSql, string $sql, ?OrderByClause $orderByClause): string
{
if (!$orderByClause) {
return $sql;
}
return sprintf('SELECT DISTINCT %s FROM (%s) dctrn_result', implode(', ', $sqlIdentifier), $this->recreateInnerSql($orderByClause, $sqlIdentifier, $innerSql));
}
private function recreateInnerSql(OrderByClause $orderByClause, array $identifiers, string $innerSql): string
{
[$searchPatterns, $replacements] = $this->generateSqlAliasReplacements();
$orderByItems = [];
foreach ($orderByClause->orderByItems as $orderByItem) {
$orderByItemString = preg_replace($searchPatterns, $replacements, $this->walkOrderByItem($orderByItem));
$orderByItems[] = $orderByItemString;
$identifier = substr($orderByItemString, 0, strrpos($orderByItemString, ' '));
if (!in_array($identifier, $identifiers, \true)) {
$identifiers[] = $identifier;
}
}
return $sql = sprintf('SELECT DISTINCT %s FROM (%s) dctrn_result_inner ORDER BY %s', implode(', ', $identifiers), $innerSql, implode(', ', $orderByItems));
}
private function generateSqlAliasReplacements(): array
{
$aliasMap = $searchPatterns = $replacements = $metadataList = [];
foreach (array_keys($this->rsm->aliasMap) as $dqlAlias) {
$metadataList[$dqlAlias] = $class = $this->getMetadataForDqlAlias($dqlAlias);
$aliasMap[$dqlAlias] = $this->getSQLTableAlias($class->getTableName(), $dqlAlias);
}
foreach ($this->rsm->fieldMappings as $fieldAlias => $fieldName) {
$dqlAliasForFieldAlias = $this->rsm->columnOwnerMap[$fieldAlias];
$class = $metadataList[$dqlAliasForFieldAlias];
if (!isset($class->fieldMappings[$fieldName])) {
continue;
}
$fieldMapping = $class->fieldMappings[$fieldName];
$columnName = $this->quoteStrategy->getColumnName($fieldName, $metadataList[$dqlAliasForFieldAlias], $this->em->getConnection()->getDatabasePlatform());
$sqlTableAliasForFieldAlias = $aliasMap[$dqlAliasForFieldAlias];
if (isset($fieldMapping['declared']) && $fieldMapping['declared'] !== $class->name) {
$otherClassMetadata = $this->em->getClassMetadata($fieldMapping['declared']);
if (!$otherClassMetadata->isMappedSuperclass) {
$sqlTableAliasForFieldAlias = $this->getSQLTableAlias($otherClassMetadata->getTableName(), $dqlAliasForFieldAlias);
}
}
$searchPatterns[] = sprintf(self::ORDER_BY_PATH_EXPRESSION, $sqlTableAliasForFieldAlias, $columnName);
$replacements[] = $fieldAlias;
}
return [$searchPatterns, $replacements];
}
public function getOrderByPathExpressions()
{
return $this->orderByPathExpressions;
}
private function getInnerSQL(SelectStatement $AST): string
{
$hiddens = [];
foreach ($AST->selectClause->selectExpressions as $idx => $expr) {
$hiddens[$idx] = $expr->hiddenAliasResultVariable;
$expr->hiddenAliasResultVariable = \false;
}
$innerSql = parent::walkSelectStatement($AST);
foreach ($AST->selectClause->selectExpressions as $idx => $expr) {
$expr->hiddenAliasResultVariable = $hiddens[$idx];
}
return $innerSql;
}
private function getSQLIdentifier(SelectStatement $AST): array
{
$from = $AST->fromClause->identificationVariableDeclarations;
if (count($from) !== 1) {
throw new RuntimeException('Cannot count query which selects two FROM components, cannot make distinction');
}
$fromRoot = reset($from);
$rootAlias = $fromRoot->rangeVariableDeclaration->aliasIdentificationVariable;
$rootClass = $this->getMetadataForDqlAlias($rootAlias);
$rootIdentifier = $rootClass->identifier;
$sqlIdentifier = [];
foreach ($rootIdentifier as $property) {
if (isset($rootClass->fieldMappings[$property])) {
foreach (array_keys($this->rsm->fieldMappings, $property, \true) as $alias) {
if ($this->rsm->columnOwnerMap[$alias] === $rootAlias) {
$sqlIdentifier[$property] = $alias;
}
}
}
if (isset($rootClass->associationMappings[$property])) {
$joinColumn = $rootClass->associationMappings[$property]['joinColumns'][0]['name'];
foreach (array_keys($this->rsm->metaMappings, $joinColumn, \true) as $alias) {
if ($this->rsm->columnOwnerMap[$alias] === $rootAlias) {
$sqlIdentifier[$property] = $alias;
}
}
}
}
if (count($sqlIdentifier) === 0) {
throw new RuntimeException('The Paginator does not support Queries which only yield ScalarResults.');
}
if (count($rootIdentifier) !== count($sqlIdentifier)) {
throw new RuntimeException(sprintf('Not all identifier properties can be found in the ResultSetMapping: %s', implode(', ', array_diff($rootIdentifier, array_keys($sqlIdentifier)))));
}
return $sqlIdentifier;
}
public function walkPathExpression($pathExpr)
{
if (!$this->inSubSelect && !$this->platformSupportsRowNumber() && !in_array($pathExpr, $this->orderByPathExpressions, \true)) {
$this->orderByPathExpressions[] = $pathExpr;
}
return parent::walkPathExpression($pathExpr);
}
public function walkSubSelect($subselect)
{
$this->inSubSelect = \true;
$sql = parent::walkSubselect($subselect);
$this->inSubSelect = \false;
return $sql;
}
}
