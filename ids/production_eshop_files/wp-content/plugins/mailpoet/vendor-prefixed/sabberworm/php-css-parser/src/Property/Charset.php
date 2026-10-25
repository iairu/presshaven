<?php
declare (strict_types=1);
namespace MailPoetVendor\Sabberworm\CSS\Property;
if (!defined('ABSPATH')) exit;
use MailPoetVendor\Sabberworm\CSS\Comment\CommentContainer;
use MailPoetVendor\Sabberworm\CSS\OutputFormat;
use MailPoetVendor\Sabberworm\CSS\Position\Position;
use MailPoetVendor\Sabberworm\CSS\Position\Positionable;
use MailPoetVendor\Sabberworm\CSS\ShortClassNameProvider;
use MailPoetVendor\Sabberworm\CSS\Value\CSSString;
class Charset implements AtRule, Positionable
{
use CommentContainer;
use Position;
use ShortClassNameProvider;
private $charset;
public function __construct(CSSString $charset, ?int $lineNumber = null)
{
$this->charset = $charset;
$this->setPosition($lineNumber);
}
public function setCharset($charset): void
{
$charset = $charset instanceof CSSString ? $charset : new CSSString($charset);
$this->charset = $charset;
}
public function getCharset(): string
{
return $this->charset->getString();
}
public function render(OutputFormat $outputFormat): string
{
return "{$outputFormat->getFormatter()->comments($this)}@charset {$this->charset->render($outputFormat)};";
}
public function atRuleName(): string
{
return 'charset';
}
public function atRuleArgs(): CSSString
{
return $this->charset;
}
public function getArrayRepresentation(): array
{
return ['class' => $this->getShortClassName(), 'charset' => $this->charset->getArrayRepresentation()];
}
}
