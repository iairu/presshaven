<?php
declare (strict_types=1);
namespace MailPoetVendor\Sabberworm\CSS\Property;
if (!defined('ABSPATH')) exit;
use MailPoetVendor\Sabberworm\CSS\Comment\CommentContainer;
use MailPoetVendor\Sabberworm\CSS\OutputFormat;
use MailPoetVendor\Sabberworm\CSS\Position\Position;
use MailPoetVendor\Sabberworm\CSS\Position\Positionable;
use MailPoetVendor\Sabberworm\CSS\ShortClassNameProvider;
use MailPoetVendor\Sabberworm\CSS\Value\URL;
class Import implements AtRule, Positionable
{
use CommentContainer;
use Position;
use ShortClassNameProvider;
private $location;
private $mediaQuery;
public function __construct(URL $location, ?string $mediaQuery, ?int $lineNumber = null)
{
$this->location = $location;
$this->mediaQuery = $mediaQuery;
$this->setPosition($lineNumber);
}
public function setLocation(URL $location): void
{
$this->location = $location;
}
public function getLocation(): URL
{
return $this->location;
}
public function render(OutputFormat $outputFormat): string
{
return $outputFormat->getFormatter()->comments($this) . '@import ' . $this->location->render($outputFormat) . ($this->mediaQuery === null ? '' : ' ' . $this->mediaQuery) . ';';
}
public function atRuleName(): string
{
return 'import';
}
public function atRuleArgs(): array
{
$result = [$this->location];
if (\is_string($this->mediaQuery) && $this->mediaQuery !== '') {
$result[] = $this->mediaQuery;
}
return $result;
}
public function getMediaQuery(): ?string
{
return $this->mediaQuery;
}
public function getArrayRepresentation(): array
{
return [
'class' => $this->getShortClassName(),
'uri' => $this->location->getArrayRepresentation(),
];
}
}
