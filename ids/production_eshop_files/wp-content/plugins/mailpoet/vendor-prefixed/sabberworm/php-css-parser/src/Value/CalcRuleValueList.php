<?php
declare (strict_types=1);
namespace MailPoetVendor\Sabberworm\CSS\Value;
if (!defined('ABSPATH')) exit;
use MailPoetVendor\Sabberworm\CSS\OutputFormat;
class CalcRuleValueList extends RuleValueList
{
public function __construct(?int $lineNumber = null)
{
parent::__construct(',', $lineNumber);
}
public function render(OutputFormat $outputFormat): string
{
return $outputFormat->getFormatter()->implode(' ', $this->components);
}
public function getArrayRepresentation(): array
{
throw new \BadMethodCallException('`getArrayRepresentation` is not yet implemented for `' . self::class . '`');
}
}
