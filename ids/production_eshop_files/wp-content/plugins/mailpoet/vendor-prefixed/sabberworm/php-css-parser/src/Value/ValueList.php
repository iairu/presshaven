<?php
declare (strict_types=1);
namespace MailPoetVendor\Sabberworm\CSS\Value;
if (!defined('ABSPATH')) exit;
use MailPoetVendor\Sabberworm\CSS\OutputFormat;
use MailPoetVendor\Sabberworm\CSS\ShortClassNameProvider;
abstract class ValueList extends Value
{
use ShortClassNameProvider;
protected $components;
protected $separator;
public function __construct($components = [], $separator = ',', ?int $lineNumber = null)
{
parent::__construct($lineNumber);
if (!\is_array($components)) {
$components = [$components];
}
$this->components = $components;
$this->separator = $separator;
}
public function addListComponent($component): void
{
$this->components[] = $component;
}
public function getListComponents(): array
{
return $this->components;
}
public function setListComponents(array $components): void
{
$this->components = $components;
}
public function getListSeparator(): string
{
return $this->separator;
}
public function setListSeparator(string $separator): void
{
$this->separator = $separator;
}
public function render(OutputFormat $outputFormat): string
{
$formatter = $outputFormat->getFormatter();
return $formatter->implode($formatter->spaceBeforeListArgumentSeparator($this->separator) . $this->separator . $formatter->spaceAfterListArgumentSeparator($this->separator), $this->components);
}
public function getArrayRepresentation(): array
{
return ['class' => $this->getShortClassName(), 'components' => \array_map(
function ($component): array {
if (\is_string($component)) {
return ['class' => 'string', 'value' => $component];
}
return $component->getArrayRepresentation();
},
$this->components
), 'separator' => $this->separator];
}
}
