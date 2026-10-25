<?php
declare (strict_types=1);
namespace MailPoetVendor\Sabberworm\CSS\RuleSet;
if (!defined('ABSPATH')) exit;
use MailPoetVendor\Sabberworm\CSS\OutputFormat;
use MailPoetVendor\Sabberworm\CSS\Property\AtRule;
class AtRuleSet extends RuleSet implements AtRule
{
private $type;
private $arguments;
public function __construct(string $type, string $arguments = '', ?int $lineNumber = null)
{
parent::__construct($lineNumber);
$this->type = $type;
$this->arguments = $arguments;
}
public function atRuleName(): string
{
return $this->type;
}
public function atRuleArgs(): string
{
return $this->arguments;
}
public function render(OutputFormat $outputFormat): string
{
$formatter = $outputFormat->getFormatter();
$result = $formatter->comments($this);
$arguments = $this->arguments;
if ($arguments !== '') {
$arguments = ' ' . $arguments;
}
$result .= "@{$this->type}{$arguments}{$formatter->spaceBeforeOpeningBrace()}{";
$result .= $this->renderDeclarations($outputFormat);
$result .= '}';
return $result;
}
public function getArrayRepresentation(): array
{
$arrayRepresentation = parent::getArrayRepresentation();
$arrayRepresentation['atRuleName'] = $this->type;
$arrayRepresentation['arguments'] = $this->arguments;
return $arrayRepresentation;
}
}
