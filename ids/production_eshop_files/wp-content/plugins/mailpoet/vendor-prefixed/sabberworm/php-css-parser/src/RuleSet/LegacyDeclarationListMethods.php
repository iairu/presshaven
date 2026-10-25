<?php
declare (strict_types=1);
namespace MailPoetVendor\Sabberworm\CSS\RuleSet;
if (!defined('ABSPATH')) exit;
use MailPoetVendor\Sabberworm\CSS\Property\Declaration;
trait LegacyDeclarationListMethods
{
public function addRule(Declaration $declarationToAdd, ?Declaration $sibling = null): void
{
$this->addDeclaration($declarationToAdd, $sibling);
}
public function removeRule(Declaration $declarationToRemove): void
{
$this->removeDeclaration($declarationToRemove);
}
public function removeMatchingRules(string $searchPattern): void
{
$this->removeMatchingDeclarations($searchPattern);
}
public function removeAllRules(): void
{
$this->removeAllDeclarations();
}
public function setRules(array $declarations): void
{
$this->setDeclarations($declarations);
}
public function getRules(?string $searchPattern = null): array
{
return $this->getDeclarations($searchPattern);
}
public function getRulesAssoc(?string $searchPattern = null): array
{
return $this->getDeclarationsAssociative($searchPattern);
}
}
