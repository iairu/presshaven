<?php
declare (strict_types=1);
namespace MailPoetVendor\Sabberworm\CSS\RuleSet;
if (!defined('ABSPATH')) exit;
use MailPoetVendor\Sabberworm\CSS\Comment\CommentContainer;
use MailPoetVendor\Sabberworm\CSS\CSSElement;
use MailPoetVendor\Sabberworm\CSS\CSSList\CSSListItem;
use MailPoetVendor\Sabberworm\CSS\OutputFormat;
use MailPoetVendor\Sabberworm\CSS\Parsing\ParserState;
use MailPoetVendor\Sabberworm\CSS\Parsing\UnexpectedEOFException;
use MailPoetVendor\Sabberworm\CSS\Parsing\UnexpectedTokenException;
use MailPoetVendor\Sabberworm\CSS\Position\Position;
use MailPoetVendor\Sabberworm\CSS\Position\Positionable;
use MailPoetVendor\Sabberworm\CSS\Property\Declaration;
use MailPoetVendor\Sabberworm\CSS\ShortClassNameProvider;
class RuleSet implements CSSElement, CSSListItem, Positionable, DeclarationList
{
use CommentContainer;
use LegacyDeclarationListMethods;
use Position;
use ShortClassNameProvider;
private $declarations = [];
public function __construct(?int $lineNumber = null)
{
$this->setPosition($lineNumber);
}
public static function parseRuleSet(ParserState $parserState, RuleSet $ruleSet): void
{
while ($parserState->comes(';')) {
$parserState->consume(';');
}
while (\true) {
$commentsBeforeDeclaration = [];
$parserState->consumeWhiteSpace($commentsBeforeDeclaration);
if ($parserState->comes('}')) {
break;
}
$declaration = null;
if ($parserState->getSettings()->usesLenientParsing()) {
try {
$declaration = Declaration::parse($parserState, $commentsBeforeDeclaration);
} catch (UnexpectedTokenException $e) {
try {
$consumedText = $parserState->consumeUntil(["\n", ';', '}'], \true);
if ($parserState->streql(\substr($consumedText, -1), '}')) {
$parserState->backtrack(1);
} else {
while ($parserState->comes(';')) {
$parserState->consume(';');
}
}
} catch (UnexpectedTokenException $e) {
return;
}
}
} else {
$declaration = Declaration::parse($parserState, $commentsBeforeDeclaration);
}
if ($declaration instanceof Declaration) {
$ruleSet->addDeclaration($declaration);
}
}
$parserState->consume('}');
}
public function addDeclaration(Declaration $declarationToAdd, ?Declaration $sibling = null): void
{
$propertyName = $declarationToAdd->getPropertyName();
if (!isset($this->declarations[$propertyName])) {
$this->declarations[$propertyName] = [];
}
$position = \count($this->declarations[$propertyName]);
if ($sibling !== null) {
$siblingPosition = \array_search($sibling, $this->declarations[$propertyName], \true);
if ($siblingPosition !== \false) {
$siblingIsInSet = \true;
$position = $siblingPosition;
} else {
$siblingIsInSet = $this->hasDeclaration($sibling);
if ($siblingIsInSet) {
foreach ($this->declarations[$propertyName] as $index => $declaration) {
if (self::comparePositionable($declaration, $sibling) >= 0) {
$position = $index;
break;
}
}
}
}
if ($siblingIsInSet) {
$siblingLineNumber = $sibling->getLineNumber();
$siblingColumnNumber = $sibling->getColumnNumber();
foreach ($this->declarations as $declarationsForAProperty) {
foreach ($declarationsForAProperty as $declaration) {
if ($declaration->getLineNumber() === $siblingLineNumber && $declaration->getColumnNumber() >= $siblingColumnNumber) {
$declaration->setPosition($siblingLineNumber, $declaration->getColumnNumber() + 1);
}
}
}
$declarationToAdd->setPosition($siblingLineNumber, $siblingColumnNumber);
}
}
if ($declarationToAdd->getLineNumber() === null) {
$columnNumber = $declarationToAdd->getColumnNumber() ?? 0;
$declarations = $this->getDeclarations();
$declarationsCount = \count($declarations);
if ($declarationsCount > 0) {
$last = $declarations[$declarationsCount - 1];
$lastsLineNumber = $last->getLineNumber();
if (!\is_int($lastsLineNumber)) {
throw new \UnexpectedValueException('A Declaration without a line number was found during addDeclaration', 1750718399);
}
$declarationToAdd->setPosition($lastsLineNumber + 1, $columnNumber);
} else {
$declarationToAdd->setPosition(1, $columnNumber);
}
} elseif ($declarationToAdd->getColumnNumber() === null) {
$declarationToAdd->setPosition($declarationToAdd->getLineNumber(), 0);
}
\array_splice($this->declarations[$propertyName], $position, 0, [$declarationToAdd]);
}
public function getDeclarations(?string $searchPattern = null): array
{
$result = [];
foreach ($this->declarations as $propertyName => $declarations) {
if ($searchPattern === null || $propertyName === $searchPattern || \strrpos($searchPattern, '-') === \strlen($searchPattern) - \strlen('-') && (\strpos($propertyName, $searchPattern) === 0 || $propertyName === \substr($searchPattern, 0, -1))) {
$result = \array_merge($result, $declarations);
}
}
\usort($result, [self::class, 'comparePositionable']);
return $result;
}
public function setDeclarations(array $declarations): void
{
$this->declarations = [];
foreach ($declarations as $declaration) {
$this->addDeclaration($declaration);
}
}
public function getDeclarationsAssociative(?string $searchPattern = null): array
{
$result = [];
foreach ($this->getDeclarations($searchPattern) as $declaration) {
$result[$declaration->getPropertyName()] = $declaration;
}
return $result;
}
public function removeDeclaration(Declaration $declarationToRemove): void
{
$nameOfPropertyToRemove = $declarationToRemove->getPropertyName();
if (!isset($this->declarations[$nameOfPropertyToRemove])) {
return;
}
foreach ($this->declarations[$nameOfPropertyToRemove] as $key => $declaration) {
if ($declaration === $declarationToRemove) {
unset($this->declarations[$nameOfPropertyToRemove][$key]);
}
}
}
public function removeMatchingDeclarations(string $searchPattern): void
{
foreach ($this->declarations as $propertyName => $declarations) {
if ($propertyName === $searchPattern || \strrpos($searchPattern, '-') === \strlen($searchPattern) - \strlen('-') && (\strpos($propertyName, $searchPattern) === 0 || $propertyName === \substr($searchPattern, 0, -1))) {
unset($this->declarations[$propertyName]);
}
}
}
public function removeAllDeclarations(): void
{
$this->declarations = [];
}
public function render(OutputFormat $outputFormat): string
{
return $this->renderDeclarations($outputFormat);
}
protected function renderDeclarations(OutputFormat $outputFormat): string
{
$result = '';
$isFirst = \true;
$nextLevelFormat = $outputFormat->nextLevel();
foreach ($this->getDeclarations() as $declaration) {
$nextLevelFormatter = $nextLevelFormat->getFormatter();
$renderedDeclaration = $nextLevelFormatter->safely(static function () use ($declaration, $nextLevelFormat): string {
return $declaration->render($nextLevelFormat);
});
if ($renderedDeclaration === null) {
continue;
}
if ($isFirst) {
$isFirst = \false;
$result .= $nextLevelFormatter->spaceBeforeRules();
} else {
$result .= $nextLevelFormatter->spaceBetweenRules();
}
$result .= $renderedDeclaration;
}
$formatter = $outputFormat->getFormatter();
if (!$isFirst) {
$result .= $formatter->spaceAfterRules();
}
return $formatter->removeLastSemicolon($result);
}
public function getArrayRepresentation(): array
{
$declarationsArrayRepresentation = [];
foreach ($this->declarations as $propertyName => $declarationsForOneProperty) {
$declarationsArrayRepresentation[$propertyName] = \array_map(function (Declaration $declaration): array {
return $declaration->getArrayRepresentation();
}, $declarationsForOneProperty);
}
return ['class' => $this->getShortClassName(), 'declarations' => $declarationsArrayRepresentation];
}
private static function comparePositionable(Positionable $first, Positionable $second): int
{
$firstsLineNumber = $first->getLineNumber();
$secondsLineNumber = $second->getLineNumber();
if (!\is_int($firstsLineNumber) || !\is_int($secondsLineNumber)) {
throw new \UnexpectedValueException('A Declaration without a line number was passed to comparePositionable', 1750637683);
}
if ($firstsLineNumber === $secondsLineNumber) {
$firstsColumnNumber = $first->getColumnNumber();
$secondsColumnNumber = $second->getColumnNumber();
if (!\is_int($firstsColumnNumber) || !\is_int($secondsColumnNumber)) {
throw new \UnexpectedValueException('A Declaration without a column number was passed to comparePositionable', 1750637761);
}
return $firstsColumnNumber - $secondsColumnNumber;
}
return $firstsLineNumber - $secondsLineNumber;
}
private function hasDeclaration(Declaration $declaration): bool
{
foreach ($this->declarations as $declarationsForAProperty) {
if (\in_array($declaration, $declarationsForAProperty, \true)) {
return \true;
}
}
return \false;
}
}
