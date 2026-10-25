<?php
namespace MailPoetVendor\Doctrine\DBAL\Schema;
if (!defined('ABSPATH')) exit;
use MailPoetVendor\Doctrine\DBAL\Platforms\AbstractPlatform;
use InvalidArgumentException;
use function array_filter;
use function array_keys;
use function array_map;
use function array_search;
use function array_shift;
use function count;
use function strtolower;
class Index extends AbstractAsset implements Constraint
{
protected $_columns = [];
protected $_isUnique = \false;
protected $_isPrimary = \false;
protected $_flags = [];
private array $options = [];
public function __construct($name, array $columns, $isUnique = \false, $isPrimary = \false, array $flags = [], array $options = [])
{
$isUnique = $isUnique || $isPrimary;
$this->_setName($name);
$this->_isUnique = $isUnique;
$this->_isPrimary = $isPrimary;
$this->options = $options;
foreach ($columns as $column) {
$this->_addColumn($column);
}
foreach ($flags as $flag) {
$this->addFlag($flag);
}
}
protected function _addColumn(string $column): void
{
$this->_columns[$column] = new Identifier($column);
}
public function getColumns()
{
return array_keys($this->_columns);
}
public function getQuotedColumns(AbstractPlatform $platform)
{
$subParts = $platform->supportsColumnLengthIndexes() && $this->hasOption('lengths') ? $this->getOption('lengths') : [];
$columns = [];
foreach ($this->_columns as $column) {
$length = array_shift($subParts);
$quotedColumn = $column->getQuotedName($platform);
if ($length !== null) {
$quotedColumn .= '(' . $length . ')';
}
$columns[] = $quotedColumn;
}
return $columns;
}
public function getUnquotedColumns()
{
return array_map([$this, 'trimQuotes'], $this->getColumns());
}
public function isSimpleIndex()
{
return !$this->_isPrimary && !$this->_isUnique;
}
public function isUnique()
{
return $this->_isUnique;
}
public function isPrimary()
{
return $this->_isPrimary;
}
public function hasColumnAtPosition($name, $pos = 0)
{
$name = $this->trimQuotes(strtolower($name));
$indexColumns = array_map('strtolower', $this->getUnquotedColumns());
return array_search($name, $indexColumns, \true) === $pos;
}
public function spansColumns(array $columnNames)
{
$columns = $this->getColumns();
$numberOfColumns = count($columns);
$sameColumns = \true;
for ($i = 0; $i < $numberOfColumns; $i++) {
if (isset($columnNames[$i]) && $this->trimQuotes(strtolower($columns[$i])) === $this->trimQuotes(strtolower($columnNames[$i]))) {
continue;
}
$sameColumns = \false;
}
return $sameColumns;
}
public function isFullfilledBy(Index $other)
{
return $this->isFulfilledBy($other);
}
public function isFulfilledBy(Index $other): bool
{
if (count($other->getColumns()) !== count($this->getColumns())) {
return \false;
}
$sameColumns = $this->spansColumns($other->getColumns());
if ($sameColumns) {
if (!$this->samePartialIndex($other)) {
return \false;
}
if (!$this->hasSameColumnLengths($other)) {
return \false;
}
if (!$this->isUnique() && !$this->isPrimary()) {
return \true;
}
if ($other->isPrimary() !== $this->isPrimary()) {
return \false;
}
return $other->isUnique() === $this->isUnique();
}
return \false;
}
public function overrules(Index $other)
{
if ($other->isPrimary()) {
return \false;
}
if ($this->isSimpleIndex() && $other->isUnique()) {
return \false;
}
return $this->spansColumns($other->getColumns()) && ($this->isPrimary() || $this->isUnique()) && $this->samePartialIndex($other);
}
public function getFlags()
{
return array_keys($this->_flags);
}
public function addFlag($flag)
{
$this->_flags[strtolower($flag)] = \true;
return $this;
}
public function hasFlag($flag)
{
return isset($this->_flags[strtolower($flag)]);
}
public function removeFlag($flag)
{
unset($this->_flags[strtolower($flag)]);
}
public function hasOption($name)
{
return isset($this->options[strtolower($name)]);
}
public function getOption($name)
{
return $this->options[strtolower($name)];
}
public function getOptions()
{
return $this->options;
}
private function samePartialIndex(Index $other): bool
{
if ($this->hasOption('where') && $other->hasOption('where') && $this->getOption('where') === $other->getOption('where')) {
return \true;
}
return !$this->hasOption('where') && !$other->hasOption('where');
}
private function hasSameColumnLengths(self $other): bool
{
$filter = static function (?int $length): bool {
return $length !== null;
};
return array_filter($this->options['lengths'] ?? [], $filter) === array_filter($other->options['lengths'] ?? [], $filter);
}
}
