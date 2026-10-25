<?php
declare (strict_types=1);
namespace MailPoetVendor\Doctrine\Persistence\Reflection;
if (!defined('ABSPATH')) exit;
use BackedEnum;
use ReflectionProperty;
use ReturnTypeWillChange;
use function array_map;
use function is_array;
use function reset;
class EnumReflectionProperty extends ReflectionProperty
{
private $originalReflectionProperty;
private $enumType;
public function __construct(ReflectionProperty $originalReflectionProperty, string $enumType)
{
parent::__construct($originalReflectionProperty->class, $originalReflectionProperty->name);
$this->originalReflectionProperty = $originalReflectionProperty;
$this->enumType = $enumType;
}
#[ReturnTypeWillChange]
public function getValue($object = null)
{
if ($object === null) {
return null;
}
$enum = $this->originalReflectionProperty->getValue($object);
if ($enum === null) {
return null;
}
return $this->fromEnum($enum);
}
public function setValue($object, $value = null): void
{
if ($value !== null) {
$value = $this->toEnum($value);
}
$this->originalReflectionProperty->setValue($object, $value);
}
private function fromEnum($enum)
{
if (is_array($enum)) {
return array_map(static function (BackedEnum $enum) {
return $enum->value;
}, $enum);
}
return $enum->value;
}
private function toEnum($value)
{
if ($value instanceof BackedEnum) {
return $value;
}
if (is_array($value)) {
$v = reset($value);
if ($v instanceof BackedEnum) {
return $value;
}
return array_map([$this->enumType, 'from'], $value);
}
return $this->enumType::from($value);
}
}
