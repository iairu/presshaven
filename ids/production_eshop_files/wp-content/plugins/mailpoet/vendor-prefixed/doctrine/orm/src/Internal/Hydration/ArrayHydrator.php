<?php
declare (strict_types=1);
namespace MailPoetVendor\Doctrine\ORM\Internal\Hydration;
if (!defined('ABSPATH')) exit;
use MailPoetVendor\Doctrine\ORM\Mapping\ClassMetadata;
use function count;
use function end;
use function is_array;
use function key;
use function reset;
class ArrayHydrator extends AbstractHydrator
{
private $rootAliases = [];
private $isSimpleQuery = \false;
private $identifierMap = [];
private $resultPointers = [];
private $idTemplate = [];
private $resultCounter = 0;
protected function prepare()
{
$this->isSimpleQuery = count($this->resultSetMapping()->aliasMap) <= 1;
foreach ($this->resultSetMapping()->aliasMap as $dqlAlias => $className) {
$this->identifierMap[$dqlAlias] = [];
$this->resultPointers[$dqlAlias] = [];
$this->idTemplate[$dqlAlias] = '';
}
}
protected function hydrateAllData()
{
$result = [];
while ($data = $this->statement()->fetchAssociative()) {
$this->hydrateRowData($data, $result);
}
return $result;
}
protected function hydrateRowData(array $row, array &$result)
{
$id = $this->idTemplate;
$nonemptyComponents = [];
$rowData = $this->gatherRowData($row, $id, $nonemptyComponents);
foreach ($rowData['data'] as $dqlAlias => $data) {
$index = \false;
if (isset($this->resultSetMapping()->parentAliasMap[$dqlAlias])) {
$parent = $this->resultSetMapping()->parentAliasMap[$dqlAlias];
$path = $parent . '.' . $dqlAlias;
if (!isset($nonemptyComponents[$parent])) {
continue;
}
if ($this->resultSetMapping()->isMixed && isset($this->rootAliases[$parent])) {
$first = reset($this->resultPointers);
$baseElement =& $this->resultPointers[$parent][key($first)];
} elseif (isset($this->resultPointers[$parent])) {
$baseElement =& $this->resultPointers[$parent];
} else {
unset($this->resultPointers[$dqlAlias]);
continue;
}
$relationAlias = $this->resultSetMapping()->relationMap[$dqlAlias];
$parentClass = $this->_metadataCache[$this->resultSetMapping()->aliasMap[$parent]];
$relation = $parentClass->associationMappings[$relationAlias];
if (!($relation['type'] & ClassMetadata::TO_ONE)) {
$oneToOne = \false;
if (!isset($baseElement[$relationAlias])) {
$baseElement[$relationAlias] = [];
}
if (isset($nonemptyComponents[$dqlAlias])) {
$indexExists = isset($this->identifierMap[$path][$id[$parent]][$id[$dqlAlias]]);
$index = $indexExists ? $this->identifierMap[$path][$id[$parent]][$id[$dqlAlias]] : \false;
$indexIsValid = $index !== \false ? isset($baseElement[$relationAlias][$index]) : \false;
if (!$indexExists || !$indexIsValid) {
$element = $data;
if (isset($this->resultSetMapping()->indexByMap[$dqlAlias])) {
$baseElement[$relationAlias][$row[$this->resultSetMapping()->indexByMap[$dqlAlias]]] = $element;
} else {
$baseElement[$relationAlias][] = $element;
}
end($baseElement[$relationAlias]);
$this->identifierMap[$path][$id[$parent]][$id[$dqlAlias]] = key($baseElement[$relationAlias]);
}
}
} else {
$oneToOne = \true;
if (!isset($nonemptyComponents[$dqlAlias]) && !isset($baseElement[$relationAlias])) {
$baseElement[$relationAlias] = null;
} elseif (!isset($baseElement[$relationAlias])) {
$baseElement[$relationAlias] = $data;
}
}
$coll =& $baseElement[$relationAlias];
if (is_array($coll)) {
$this->updateResultPointer($coll, $index, $dqlAlias, $oneToOne);
}
} else {
$this->rootAliases[$dqlAlias] = \true;
$entityKey = $this->resultSetMapping()->entityMappings[$dqlAlias] ?: 0;
if (!isset($nonemptyComponents[$dqlAlias])) {
$result[] = $this->resultSetMapping()->isMixed ? [$entityKey => null] : null;
$resultKey = $this->resultCounter;
++$this->resultCounter;
continue;
}
if ($this->isSimpleQuery || !isset($this->identifierMap[$dqlAlias][$id[$dqlAlias]])) {
$element = $this->resultSetMapping()->isMixed ? [$entityKey => $data] : $data;
if (isset($this->resultSetMapping()->indexByMap[$dqlAlias])) {
$resultKey = $row[$this->resultSetMapping()->indexByMap[$dqlAlias]];
$result[$resultKey] = $element;
} else {
$resultKey = $this->resultCounter;
$result[] = $element;
++$this->resultCounter;
}
$this->identifierMap[$dqlAlias][$id[$dqlAlias]] = $resultKey;
} else {
$index = $this->identifierMap[$dqlAlias][$id[$dqlAlias]];
$resultKey = $index;
}
$this->updateResultPointer($result, $index, $dqlAlias, \false);
}
}
if (!isset($resultKey)) {
$this->resultCounter++;
}
if (isset($rowData['scalars'])) {
if (!isset($resultKey)) {
$resultKey = isset($this->resultSetMapping()->indexByMap['scalars']) ? $row[$this->resultSetMapping()->indexByMap['scalars']] : $this->resultCounter - 1;
}
foreach ($rowData['scalars'] as $name => $value) {
$result[$resultKey][$name] = $value;
}
}
if (isset($rowData['newObjects'])) {
if (!isset($resultKey)) {
$resultKey = $this->resultCounter - 1;
}
$scalarCount = isset($rowData['scalars']) ? count($rowData['scalars']) : 0;
foreach ($rowData['newObjects'] as $objIndex => $newObject) {
$class = $newObject['class'];
$args = $newObject['args'];
$obj = $class->newInstanceArgs($args);
if (count($args) === $scalarCount || $scalarCount === 0 && count($rowData['newObjects']) === 1) {
$result[$resultKey] = $obj;
continue;
}
$result[$resultKey][$objIndex] = $obj;
}
}
}
private function updateResultPointer(?array &$coll, $index, string $dqlAlias, bool $oneToOne): void
{
if ($coll === null) {
unset($this->resultPointers[$dqlAlias]);
return;
}
if ($oneToOne) {
$this->resultPointers[$dqlAlias] =& $coll;
return;
}
if ($index !== \false) {
$this->resultPointers[$dqlAlias] =& $coll[$index];
return;
}
if (!$coll) {
return;
}
end($coll);
$this->resultPointers[$dqlAlias] =& $coll[key($coll)];
}
}
