<?php
declare (strict_types=1);
namespace MailPoetVendor\Sabberworm\CSS\CSSList;
if (!defined('ABSPATH')) exit;
use MailPoetVendor\Sabberworm\CSS\CSSElement;
use MailPoetVendor\Sabberworm\CSS\Property\Declaration;
use MailPoetVendor\Sabberworm\CSS\Property\Selector;
use MailPoetVendor\Sabberworm\CSS\RuleSet\DeclarationBlock;
use MailPoetVendor\Sabberworm\CSS\RuleSet\DeclarationList;
use MailPoetVendor\Sabberworm\CSS\RuleSet\RuleSet;
use MailPoetVendor\Sabberworm\CSS\Value\CSSFunction;
use MailPoetVendor\Sabberworm\CSS\Value\Value;
use MailPoetVendor\Sabberworm\CSS\Value\ValueList;
abstract class CSSBlockList extends CSSList
{
public function getAllDeclarationBlocks(): array
{
$result = [];
foreach ($this->contents as $item) {
if ($item instanceof DeclarationBlock) {
$result[] = $item;
} elseif ($item instanceof CSSBlockList) {
$result = \array_merge($result, $item->getAllDeclarationBlocks());
}
}
return $result;
}
public function getAllRuleSets(): array
{
$result = [];
foreach ($this->contents as $item) {
if ($item instanceof RuleSet) {
$result[] = $item;
} elseif ($item instanceof CSSBlockList) {
$result = \array_merge($result, $item->getAllRuleSets());
} elseif ($item instanceof DeclarationBlock) {
$result[] = $item->getRuleSet();
}
}
return $result;
}
public function getAllValues(?CSSElement $element = null, ?string $ruleSearchPattern = null, bool $searchInFunctionArguments = \false): array
{
$element = $element ?? $this;
$result = [];
if ($element instanceof CSSBlockList) {
foreach ($element->getContents() as $contentItem) {
if ($contentItem instanceof CSSElement) {
$result = \array_merge($result, $this->getAllValues($contentItem, $ruleSearchPattern, $searchInFunctionArguments));
}
}
} elseif ($element instanceof DeclarationList) {
foreach ($element->getRules($ruleSearchPattern) as $rule) {
$result = \array_merge($result, $this->getAllValues($rule, $ruleSearchPattern, $searchInFunctionArguments));
}
} elseif ($element instanceof Declaration) {
$value = $element->getValue();
if ($value instanceof CSSElement) {
$result = \array_merge($result, $this->getAllValues($value, $ruleSearchPattern, $searchInFunctionArguments));
}
} elseif ($element instanceof ValueList) {
if ($searchInFunctionArguments || !$element instanceof CSSFunction) {
foreach ($element->getListComponents() as $component) {
if ($component instanceof CSSElement) {
$result = \array_merge($result, $this->getAllValues($component, $ruleSearchPattern, $searchInFunctionArguments));
}
}
}
} elseif ($element instanceof Value) {
$result[] = $element;
}
return $result;
}
protected function getAllSelectors(?string $specificitySearch = null): array
{
$result = [];
foreach ($this->getAllDeclarationBlocks() as $declarationBlock) {
foreach ($declarationBlock->getSelectors() as $selector) {
if ($specificitySearch === null) {
$result[] = $selector;
} else {
$comparator = '===';
$expressionParts = \explode(' ', $specificitySearch);
$targetSpecificity = $expressionParts[0];
if (\count($expressionParts) > 1) {
$comparator = $expressionParts[0];
$targetSpecificity = $expressionParts[1];
}
$targetSpecificity = (int) $targetSpecificity;
$selectorSpecificity = $selector->getSpecificity();
switch ($comparator) {
case '<=':
$comparatorMatched = $selectorSpecificity <= $targetSpecificity;
break;
case '<':
$comparatorMatched = $selectorSpecificity < $targetSpecificity;
break;
case '>=':
$comparatorMatched = $selectorSpecificity >= $targetSpecificity;
break;
case '>':
$comparatorMatched = $selectorSpecificity > $targetSpecificity;
break;
default:
$comparatorMatched = $selectorSpecificity === $targetSpecificity;
break;
}
if ($comparatorMatched) {
$result[] = $selector;
}
}
}
}
return $result;
}
}
