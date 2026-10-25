<?php
declare (strict_types=1);
namespace MailPoetVendor\Pelago\Emogrifier\Css;
if (!defined('ABSPATH')) exit;
final class RuleSetList
{
private $atRule;
private $ruleSets = [];
public function __construct(string $atRule)
{
$this->atRule = $atRule;
}
public function getAtRule(): string
{
return $this->atRule;
}
public function appendRuleSet(RuleSet $ruleSet): self
{
$this->ruleSets[] = $ruleSet;
return $this;
}
public function getRuleSets(): array
{
return $this->ruleSets;
}
}
