<?php
declare (strict_types=1);
namespace MailPoetVendor\Sabberworm\CSS\Property;
if (!defined('ABSPATH')) exit;
use MailPoetVendor\Sabberworm\CSS\Comment\CommentContainer;
use MailPoetVendor\Sabberworm\CSS\OutputFormat;
use MailPoetVendor\Sabberworm\CSS\Position\Position;
use MailPoetVendor\Sabberworm\CSS\Position\Positionable;
use MailPoetVendor\Sabberworm\CSS\ShortClassNameProvider;
class AtRuleStatement implements AtRule, Positionable
{
use CommentContainer;
use Position;
use ShortClassNameProvider;
private $type;
private $arguments;
public function __construct(string $type, string $arguments = '', ?int $lineNumber = null)
{
$this->type = $type;
$this->arguments = $arguments;
$this->setPosition($lineNumber);
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
$result .= "@{$this->type}{$arguments};";
return $result;
}
public function getArrayRepresentation(): array
{
return ['class' => $this->getShortClassName(), 'atRuleName' => $this->type, 'arguments' => $this->arguments];
}
}
