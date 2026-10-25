<?php
declare (strict_types=1);
namespace MailPoetVendor\Sabberworm\CSS\Property\Selector;
if (!defined('ABSPATH')) exit;
use MailPoetVendor\Sabberworm\CSS\Comment\Comment;
use MailPoetVendor\Sabberworm\CSS\OutputFormat;
use MailPoetVendor\Sabberworm\CSS\Parsing\ParserState;
use MailPoetVendor\Sabberworm\CSS\Parsing\UnexpectedTokenException;
use MailPoetVendor\Sabberworm\CSS\ShortClassNameProvider;
class Combinator implements Component
{
use ShortClassNameProvider;
private $value;
public function __construct(string $value)
{
$this->setValue($value);
}
public static function parse(ParserState $parserState, array &$comments = []): self
{
$consumedWhitespace = $parserState->consumeWhiteSpace($comments);
$nextToken = $parserState->peek();
if (\in_array($nextToken, ['>', '+', '~'], \true)) {
$value = $nextToken;
$parserState->consume(1);
$parserState->consumeWhiteSpace($comments);
} elseif ($consumedWhitespace !== '') {
$value = ' ';
} else {
throw new UnexpectedTokenException('combinator', $nextToken, 'literal', $parserState->currentLine());
}
return new self($value);
}
public function getValue(): string
{
return $this->value;
}
public function setValue(string $value): void
{
if (!\in_array($value, [' ', '>', '+', '~'], \true)) {
throw new \UnexpectedValueException('`' . $value . '` is not a valid selector combinator.');
}
$this->value = $value;
}
public function getSpecificity(): int
{
return 0;
}
public function render(OutputFormat $outputFormat): string
{
$spacing = $outputFormat->getSpaceAroundSelectorCombinator();
if ($this->value === ' ') {
$rendering = $spacing !== '' ? $spacing : ' ';
} else {
$rendering = $spacing . $this->value . $spacing;
}
return $rendering;
}
public function getArrayRepresentation(): array
{
return ['class' => $this->getShortClassName(), 'value' => $this->value];
}
}
