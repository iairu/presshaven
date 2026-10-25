<?php
declare (strict_types=1);
namespace MailPoetVendor\Pelago\Emogrifier\Css;
if (!defined('ABSPATH')) exit;
final class RuleSet
{
private $selectorsAsKeys;
private $declarationBlock;
public function __construct(array $selectors, string $declarationBlock)
{
$this->selectorsAsKeys = \array_flip($selectors);
$this->declarationBlock = $declarationBlock;
}
public function getSelectors(): array
{
return \array_keys($this->selectorsAsKeys);
}
public function addSelectors(array $selectors): void
{
$this->selectorsAsKeys += \array_flip($selectors);
}
public function hasEquivalentSelectors(array $selectors): bool
{
$selectorsAsKeys = \array_flip($selectors);
return \count($this->selectorsAsKeys) === \count($selectorsAsKeys) && \count($this->selectorsAsKeys) === \count($this->selectorsAsKeys + $selectorsAsKeys);
}
public function getDeclarationBlock(): string
{
return $this->declarationBlock;
}
public function setDeclarationBlock(string $declarationBlock): void
{
$this->declarationBlock = $declarationBlock;
}
}
