<?php
declare (strict_types=1);
namespace MailPoetVendor\Doctrine\ORM\Query\Filter;
if (!defined('ABSPATH')) exit;
use MailPoetVendor\Doctrine\DBAL\Connection;
use MailPoetVendor\Doctrine\DBAL\Types\Types;
use MailPoetVendor\Doctrine\ORM\EntityManagerInterface;
use MailPoetVendor\Doctrine\ORM\Mapping\ClassMetadata;
use MailPoetVendor\Doctrine\ORM\Query\ParameterTypeInferer;
use InvalidArgumentException;
use function array_map;
use function implode;
use function ksort;
use function serialize;
abstract class SQLFilter
{
private $em;
private $parameters = [];
final public function __construct(EntityManagerInterface $em)
{
$this->em = $em;
}
final public function setParameterList(string $name, array $values, string $type = Types::STRING): self
{
$this->parameters[$name] = ['value' => $values, 'type' => $type, 'is_list' => \true];
ksort($this->parameters);
$this->em->getFilters()->setFiltersStateDirty();
return $this;
}
final public function setParameter($name, $value, $type = null): self
{
if ($type === null) {
$type = ParameterTypeInferer::inferType($value);
}
$this->parameters[$name] = ['value' => $value, 'type' => $type, 'is_list' => \false];
ksort($this->parameters);
$this->em->getFilters()->setFiltersStateDirty();
return $this;
}
final public function getParameter($name)
{
if (!isset($this->parameters[$name])) {
throw new InvalidArgumentException("Parameter '" . $name . "' does not exist.");
}
if ($this->parameters[$name]['is_list']) {
throw FilterException::cannotConvertListParameterIntoSingleValue($name);
}
$param = $this->parameters[$name];
return $this->em->getConnection()->quote($param['value'], $param['type']);
}
final public function getParameterList(string $name): string
{
if (!isset($this->parameters[$name])) {
throw new InvalidArgumentException("Parameter '" . $name . "' does not exist.");
}
if ($this->parameters[$name]['is_list'] === \false) {
throw FilterException::cannotConvertSingleParameterIntoListValue($name);
}
$param = $this->parameters[$name];
$connection = $this->em->getConnection();
$quoted = array_map(static function ($value) use ($connection, $param) {
return $connection->quote($value, $param['type']);
}, $param['value']);
return implode(',', $quoted);
}
final public function hasParameter($name)
{
return isset($this->parameters[$name]);
}
final public function __toString()
{
return serialize($this->parameters);
}
final protected function getConnection(): Connection
{
return $this->em->getConnection();
}
abstract public function addFilterConstraint(ClassMetadata $targetEntity, $targetTableAlias);
}
