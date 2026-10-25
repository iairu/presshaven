<?php
declare (strict_types=1);
namespace MailPoetVendor\Pelago\Emogrifier\Utilities;
if (!defined('ABSPATH')) exit;
use MailPoetVendor\Pelago\Emogrifier\Css\RuleSet;
use MailPoetVendor\Pelago\Emogrifier\Css\RuleSetList;
final class CssConcatenator
{
private $ruleSetLists = [];
public function append(array $selectors, string $declarationBlock, string $atRule = ''): void
{
$ruleSetList = $this->getOrCreateRuleSetListToAppendTo($atRule);
$ruleSets = $ruleSetList->getRuleSets();
$lastRuleSet = \end($ruleSets);
$hasSameDeclarationsAsLastRule = $lastRuleSet instanceof RuleSet && $declarationBlock === $lastRuleSet->getDeclarationBlock();
if ($hasSameDeclarationsAsLastRule) {
$lastRuleSet->addSelectors($selectors);
} else {
$hasSameSelectorsAsLastRule = $lastRuleSet instanceof RuleSet && $lastRuleSet->hasEquivalentSelectors($selectors);
if ($hasSameSelectorsAsLastRule) {
$lastDeclarationBlockWithoutSemicolon = \rtrim(\rtrim($lastRuleSet->getDeclarationBlock()), ';');
$lastRuleSet->setDeclarationBlock($lastDeclarationBlockWithoutSemicolon . ';' . $declarationBlock);
} else {
$ruleSetList->appendRuleSet(new RuleSet($selectors, $declarationBlock));
}
}
}
public function getCss(): string
{
return \implode('', \array_map([self::class, 'getRuleSetListCss'], $this->ruleSetLists));
}
private function getOrCreateRuleSetListToAppendTo(string $atRule): RuleSetList
{
$lastRuleSetList = \end($this->ruleSetLists);
if ($lastRuleSetList instanceof RuleSetList && $atRule === $lastRuleSetList->getAtRule()) {
return $lastRuleSetList;
}
$newRuleSetList = new RuleSetList($atRule);
$this->ruleSetLists[] = $newRuleSetList;
return $newRuleSetList;
}
private static function getRuleSetListCss(RuleSetList $ruleSetList): string
{
$ruleSets = $ruleSetList->getRuleSets();
$css = \implode('', \array_map([self::class, 'getRuleSetCss'], $ruleSets));
$atRule = $ruleSetList->getAtRule();
if ($atRule !== '') {
$css = $atRule . '{' . $css . '}';
}
return $css;
}
private static function getRuleSetCss(RuleSet $ruleSet): string
{
$selectors = $ruleSet->getSelectors();
$declarationBlock = $ruleSet->getDeclarationBlock();
return \implode(',', $selectors) . '{' . $declarationBlock . '}';
}
}
