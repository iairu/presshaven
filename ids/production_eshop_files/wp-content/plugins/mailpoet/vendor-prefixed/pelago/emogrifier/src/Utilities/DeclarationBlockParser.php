<?php
declare (strict_types=1);
namespace MailPoetVendor\Pelago\Emogrifier\Utilities;
if (!defined('ABSPATH')) exit;
final class DeclarationBlockParser
{
private static $cache = [];
public static function clearCache(): void
{
self::$cache = [];
}
public static function normalizePropertyName(string $name): string
{
if (\substr($name, 0, 2) === '--') {
return $name;
}
return \strtolower($name);
}
public static function parse(string $declarationBlock): array
{
$trimmedDeclarationBlock = \trim($declarationBlock, "; \n\r\t\v\x00");
if ($trimmedDeclarationBlock === '') {
return [];
}
if (isset(self::$cache[$trimmedDeclarationBlock])) {
return self::$cache[$trimmedDeclarationBlock];
}
$preg = new Preg();
$declarations = $preg->split('/;(?!base64|charset)/', $trimmedDeclarationBlock);
$properties = [];
foreach ($declarations as $declaration) {
$matches = [];
if ($preg->match('/^(-?+[a-zA-Z_][a-zA-Z_0-9\-]*+|--[a-zA-Z_0-9\-]++)\s*+:\s*+(.++)$/s', \trim($declaration), $matches) === 0) {
continue;
}
\assert(\count($matches) >= 3);
$propertyName = $matches[1];
\assert($propertyName !== '');
$propertyValue = $matches[2];
$properties[self::normalizePropertyName($propertyName)] = $propertyValue;
}
self::$cache[$trimmedDeclarationBlock] = $properties;
return $properties;
}
}
