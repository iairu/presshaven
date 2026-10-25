<?php
declare (strict_types=1);
namespace MailPoetVendor\Sabberworm\CSS\Property;
if (!defined('ABSPATH')) exit;
use MailPoetVendor\Sabberworm\CSS\Comment\Comment;
use MailPoetVendor\Sabberworm\CSS\Comment\Commentable;
use MailPoetVendor\Sabberworm\CSS\Comment\CommentContainer;
use MailPoetVendor\Sabberworm\CSS\CSSElement;
use MailPoetVendor\Sabberworm\CSS\OutputFormat;
use MailPoetVendor\Sabberworm\CSS\Parsing\ParserState;
use MailPoetVendor\Sabberworm\CSS\Parsing\UnexpectedEOFException;
use MailPoetVendor\Sabberworm\CSS\Parsing\UnexpectedTokenException;
use MailPoetVendor\Sabberworm\CSS\Position\Position;
use MailPoetVendor\Sabberworm\CSS\Position\Positionable;
use MailPoetVendor\Sabberworm\CSS\ShortClassNameProvider;
use MailPoetVendor\Sabberworm\CSS\Value\RuleValueList;
use MailPoetVendor\Sabberworm\CSS\Value\Value;
class Declaration implements Commentable, CSSElement, Positionable
{
use CommentContainer;
use Position;
use ShortClassNameProvider;
private $propertyName;
private $value;
private $isImportant = \false;
public function __construct(string $propertyName, ?int $lineNumber = null, ?int $columnNumber = null)
{
$this->propertyName = $propertyName;
$this->setPosition($lineNumber, $columnNumber);
}
public static function parse(ParserState $parserState, array $commentsBefore = []): self
{
$comments = $commentsBefore;
$parserState->consumeWhiteSpace($comments);
$declaration = new self($parserState->parseIdentifier(!$parserState->comes('--')), $parserState->currentLine(), $parserState->currentColumn());
$parserState->consumeWhiteSpace($comments);
$declaration->setComments($comments);
$parserState->consume(':');
$value = Value::parseValue($parserState, self::getDelimitersForPropertyValue($declaration->getPropertyName()));
$declaration->setValue($value);
$parserState->consumeWhiteSpace();
if ($parserState->comes('!')) {
$parserState->consume('!');
$parserState->consumeWhiteSpace();
$parserState->consume('important');
$declaration->setIsImportant(\true);
}
$parserState->consumeWhiteSpace();
while ($parserState->comes(';')) {
$parserState->consume(';');
}
return $declaration;
}
private static function getDelimitersForPropertyValue(string $propertyName): array
{
$matchResult = \preg_match('/^font($|-)/', $propertyName);
\assert(\is_int($matchResult));
if ($matchResult === 1) {
return [',', '/', ' '];
}
switch ($propertyName) {
case 'src':
return [' ', ','];
default:
return [',', ' ', '/'];
}
}
public function setPropertyName(string $propertyName): void
{
$this->propertyName = $propertyName;
}
public function getPropertyName(): string
{
return $this->propertyName;
}
public function setRule(string $propertyName): void
{
$this->propertyName = $propertyName;
}
public function getRule(): string
{
return $this->propertyName;
}
public function getValue()
{
return $this->value;
}
public function setValue($value): void
{
$this->value = $value;
}
public function addValue($value, string $type = ' '): void
{
if (!\is_array($value)) {
$value = [$value];
}
if (!$this->value instanceof RuleValueList || $this->value->getListSeparator() !== $type) {
$currentValue = $this->value;
$this->value = new RuleValueList($type, $this->getLineNumber());
if ($currentValue !== null && $currentValue !== '') {
$this->value->addListComponent($currentValue);
}
}
foreach ($value as $valueItem) {
$this->value->addListComponent($valueItem);
}
}
public function setIsImportant(bool $isImportant): void
{
$this->isImportant = $isImportant;
}
public function getIsImportant(): bool
{
return $this->isImportant;
}
public function render(OutputFormat $outputFormat): string
{
$formatter = $outputFormat->getFormatter();
$result = "{$formatter->comments($this)}{$this->propertyName}:{$formatter->spaceAfterRuleName()}";
if ($this->value instanceof Value) {
$result .= $this->value->render($outputFormat);
} else {
$result .= $this->value;
}
if ($this->isImportant) {
$result .= ' !important';
}
$result .= ';';
return $result;
}
public function getArrayRepresentation(): array
{
return [
'class' => $this->getShortClassName(),
'propertyName' => $this->propertyName,
'propertyValue' => $this->value,
'important' => $this->isImportant,
];
}
}
