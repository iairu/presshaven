<?php
declare (strict_types=1);
namespace MailPoetVendor\Sabberworm\CSS\Value;
if (!defined('ABSPATH')) exit;
use MailPoetVendor\Sabberworm\CSS\OutputFormat;
use MailPoetVendor\Sabberworm\CSS\Parsing\ParserState;
use MailPoetVendor\Sabberworm\CSS\Parsing\SourceException;
use MailPoetVendor\Sabberworm\CSS\Parsing\UnexpectedEOFException;
use MailPoetVendor\Sabberworm\CSS\Parsing\UnexpectedTokenException;
class CSSFunction extends ValueList
{
protected $name;
public function __construct(string $name, $arguments, string $separator = ',', ?int $lineNumber = null)
{
if ($arguments instanceof RuleValueList) {
$separator = $arguments->getListSeparator();
$arguments = $arguments->getListComponents();
}
$this->name = $name;
$this->setPosition($lineNumber);
parent::__construct($arguments, $separator, $lineNumber);
}
public static function parse(ParserState $parserState, bool $ignoreCase = \false): CSSFunction
{
$name = self::parseName($parserState, $ignoreCase);
$parserState->consume('(');
$arguments = self::parseArguments($parserState);
$result = new CSSFunction($name, $arguments, ',', $parserState->currentLine());
$parserState->consume(')');
return $result;
}
private static function parseName(ParserState $parserState, bool $ignoreCase = \false): string
{
return $parserState->parseIdentifier($ignoreCase);
}
private static function parseArguments(ParserState $parserState)
{
return Value::parseValue($parserState, ['=', ' ', ',']);
}
public function getName(): string
{
return $this->name;
}
public function setName(string $name): void
{
$this->name = $name;
}
public function getArguments(): array
{
return $this->components;
}
public function render(OutputFormat $outputFormat): string
{
$arguments = parent::render($outputFormat);
return "{$this->name}({$arguments})";
}
public function getArrayRepresentation(): array
{
return \array_merge(['class' => 'placeholder', 'name' => $this->name], parent::getArrayRepresentation());
}
}
