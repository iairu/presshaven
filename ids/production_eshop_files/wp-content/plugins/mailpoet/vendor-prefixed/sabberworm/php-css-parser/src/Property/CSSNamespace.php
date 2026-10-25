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
use MailPoetVendor\Sabberworm\CSS\Value\URL;
class CSSNamespace implements AtRule, Positionable
{
use CommentContainer;
use Position;
use ShortClassNameProvider;
private $url;
private $prefix;
public function __construct($url, ?string $prefix = null, ?int $lineNumber = null)
{
$this->url = $url;
$this->prefix = $prefix;
$this->setPosition($lineNumber);
}
public function render(OutputFormat $outputFormat): string
{
return '@namespace ' . ($this->prefix === null ? '' : $this->prefix . ' ') . $this->url->render($outputFormat) . ';';
}
public function getUrl()
{
return $this->url;
}
public function getPrefix(): ?string
{
return $this->prefix;
}
public function setUrl($url): void
{
$this->url = $url;
}
public function setPrefix(string $prefix): void
{
$this->prefix = $prefix;
}
public function atRuleName(): string
{
return 'namespace';
}
public function atRuleArgs(): array
{
$result = [$this->url];
if (\is_string($this->prefix) && $this->prefix !== '') {
\array_unshift($result, $this->prefix);
}
return $result;
}
public function getArrayRepresentation(): array
{
return [
'class' => $this->getShortClassName(),
'uri' => $this->url->getArrayRepresentation(),
'prefix' => $this->prefix,
];
}
}
