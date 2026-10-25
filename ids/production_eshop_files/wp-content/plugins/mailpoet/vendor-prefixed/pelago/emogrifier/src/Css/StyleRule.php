<?php
declare (strict_types=1);
namespace MailPoetVendor\Pelago\Emogrifier\Css;
if (!defined('ABSPATH')) exit;
use MailPoetVendor\Sabberworm\CSS\OutputFormat;
use MailPoetVendor\Sabberworm\CSS\Property\Selector;
use MailPoetVendor\Sabberworm\CSS\RuleSet\DeclarationBlock;
final class StyleRule
{
private $declarationBlock;
private $containingAtRule;
public function __construct(DeclarationBlock $declarationBlock, string $containingAtRule = '')
{
$this->declarationBlock = $declarationBlock;
$this->containingAtRule = \trim($containingAtRule);
}
public function getSelectors(): array
{
$selectors = $this->declarationBlock->getSelectors();
return \array_map(static function (Selector $selector): string {
$renderedSelector = $selector->render(OutputFormat::createCompact());
\assert($renderedSelector !== '');
return $renderedSelector;
}, $selectors);
}
public function getDeclarationsAsText(): string
{
$declarations = $this->declarationBlock->getDeclarations();
$renderedDeclarations = [];
$outputFormat = OutputFormat::create();
foreach ($declarations as $declaration) {
$renderedDeclarations[] = $declaration->render($outputFormat);
}
return \implode(' ', $renderedDeclarations);
}
public function hasAtLeastOneDeclaration(): bool
{
return $this->declarationBlock->getDeclarations() !== [];
}
public function getContainingAtRule(): string
{
return $this->containingAtRule;
}
public function hasContainingAtRule(): bool
{
return $this->getContainingAtRule() !== '';
}
}
