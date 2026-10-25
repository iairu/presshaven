<?php
declare (strict_types=1);
namespace MailPoetVendor\Sabberworm\CSS\RuleSet;
if (!defined('ABSPATH')) exit;
use MailPoetVendor\Sabberworm\CSS\Property\Declaration;
interface DeclarationList
{
public function addDeclaration(Declaration $declarationToAdd, ?Declaration $sibling = null): void;
public function removeDeclaration(Declaration $declarationToRemove): void;
public function removeMatchingDeclarations(string $searchPattern): void;
public function removeAllDeclarations(): void;
public function setDeclarations(array $declarations): void;
public function getDeclarations(?string $searchPattern = null): array;
public function getDeclarationsAssociative(?string $searchPattern = null): array;
public function addRule(Declaration $declarationToAdd, ?Declaration $sibling = null): void;
public function removeRule(Declaration $declarationToRemove): void;
public function removeMatchingRules(string $searchPattern): void;
public function removeAllRules(): void;
public function setRules(array $declarations): void;
public function getRules(?string $searchPattern = null): array;
public function getRulesAssoc(?string $searchPattern = null): array;
}
