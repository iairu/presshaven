<?php
declare (strict_types=1);
namespace MailPoetVendor\Sabberworm\CSS\CSSList;
if (!defined('ABSPATH')) exit;
use MailPoetVendor\Sabberworm\CSS\Comment\CommentContainer;
use MailPoetVendor\Sabberworm\CSS\CSSElement;
use MailPoetVendor\Sabberworm\CSS\OutputFormat;
use MailPoetVendor\Sabberworm\CSS\Parsing\ParserState;
use MailPoetVendor\Sabberworm\CSS\Parsing\SourceException;
use MailPoetVendor\Sabberworm\CSS\Parsing\UnexpectedEOFException;
use MailPoetVendor\Sabberworm\CSS\Parsing\UnexpectedTokenException;
use MailPoetVendor\Sabberworm\CSS\Position\Position;
use MailPoetVendor\Sabberworm\CSS\Position\Positionable;
use MailPoetVendor\Sabberworm\CSS\Property\AtRule;
use MailPoetVendor\Sabberworm\CSS\Property\AtRuleStatement;
use MailPoetVendor\Sabberworm\CSS\Property\Charset;
use MailPoetVendor\Sabberworm\CSS\Property\CSSNamespace;
use MailPoetVendor\Sabberworm\CSS\Property\Import;
use MailPoetVendor\Sabberworm\CSS\Property\Selector;
use MailPoetVendor\Sabberworm\CSS\RuleSet\AtRuleSet;
use MailPoetVendor\Sabberworm\CSS\RuleSet\DeclarationBlock;
use MailPoetVendor\Sabberworm\CSS\RuleSet\RuleSet;
use MailPoetVendor\Sabberworm\CSS\Value\CSSString;
use MailPoetVendor\Sabberworm\CSS\Value\URL;
use MailPoetVendor\Sabberworm\CSS\Value\Value;
abstract class CSSList implements CSSElement, CSSListItem, Positionable
{
use CommentContainer;
use Position;
protected $contents = [];
public function __construct(?int $lineNumber = null)
{
$this->setPosition($lineNumber);
}
public static function parseList(ParserState $parserState, CSSList $list): void
{
$isRoot = $list instanceof Document;
$usesLenientParsing = $parserState->getSettings()->usesLenientParsing();
$comments = [];
$parserState->consumeWhiteSpace($comments);
while (!$parserState->isEnd()) {
$listItem = null;
if ($usesLenientParsing) {
try {
$positionBeforeParse = $parserState->currentColumn();
$listItem = self::parseListItem($parserState, $list);
} catch (UnexpectedTokenException $e) {
$listItem = \false;
if ($parserState->currentColumn() === $positionBeforeParse) {
$parserState->consume(1);
}
}
} else {
$listItem = self::parseListItem($parserState, $list);
}
if ($listItem === null) {
return;
}
if ($listItem) {
$listItem->addComments($comments);
$list->append($listItem);
}
$comments = [];
$parserState->consumeWhiteSpace($comments);
}
$list->addComments($comments);
if (!$isRoot && !$usesLenientParsing) {
throw new SourceException('Unexpected end of document', $parserState->currentLine());
}
}
private static function parseListItem(ParserState $parserState, CSSList $list)
{
$isRoot = $list instanceof Document;
if ($parserState->comes('@')) {
$atRule = self::parseAtRule($parserState);
if ($atRule instanceof Charset) {
if (!$isRoot) {
throw new UnexpectedTokenException('@charset may only occur in root document', '', 'custom', $parserState->currentLine());
}
if (\count($list->getContents()) > 0) {
throw new UnexpectedTokenException('@charset must be the first parseable token in a document', '', 'custom', $parserState->currentLine());
}
$parserState->setCharset($atRule->getCharset());
}
return $atRule;
} elseif ($parserState->comes('}')) {
if ($isRoot) {
if ($parserState->getSettings()->usesLenientParsing()) {
$parserState->consume(1);
return self::parseListItem($parserState, $list);
} else {
throw new SourceException('Unopened {', $parserState->currentLine());
}
} else {
return null;
}
} else {
return DeclarationBlock::parse($parserState, $list) ?? \false;
}
}
private static function parseAtRule(ParserState $parserState): ?CSSListItem
{
$parserState->consume('@');
$identifier = $parserState->parseIdentifier();
$identifierLineNumber = $parserState->currentLine();
$parserState->consumeWhiteSpace();
if ($identifier === 'import') {
$location = URL::parse($parserState);
$parserState->consumeWhiteSpace();
$mediaQuery = null;
if (!$parserState->comes(';')) {
$mediaQuery = \trim($parserState->consumeUntil([';', ParserState::EOF]));
if ($mediaQuery === '') {
$mediaQuery = null;
}
}
$parserState->consumeUntil([';', ParserState::EOF], \true, \true);
return new Import($location, $mediaQuery, $identifierLineNumber);
} elseif ($identifier === 'charset') {
$charsetString = CSSString::parse($parserState);
$parserState->consumeWhiteSpace();
$parserState->consumeUntil([';', ParserState::EOF], \true, \true);
return new Charset($charsetString, $identifierLineNumber);
} elseif (self::identifierIs($identifier, 'keyframes')) {
$result = new KeyFrame($identifierLineNumber);
$result->setVendorKeyFrame($identifier);
$result->setAnimationName(\trim($parserState->consumeUntil('{', \false, \true)));
CSSList::parseList($parserState, $result);
if ($parserState->comes('}')) {
$parserState->consume('}');
}
return $result;
} elseif ($identifier === 'namespace') {
$prefix = null;
$url = Value::parsePrimitiveValue($parserState);
if (!$parserState->comes(';')) {
$prefix = $url;
$url = Value::parsePrimitiveValue($parserState);
}
$parserState->consumeUntil([';', ParserState::EOF], \true, \true);
if ($prefix !== null && !\is_string($prefix)) {
throw new UnexpectedTokenException('Wrong namespace prefix', $prefix, 'custom', $identifierLineNumber);
}
if (!($url instanceof CSSString || $url instanceof URL)) {
throw new UnexpectedTokenException('Wrong namespace url of invalid type', $url, 'custom', $identifierLineNumber);
}
return new CSSNamespace($url, $prefix, $identifierLineNumber);
} else {
$arguments = \trim($parserState->consumeUntil(['{', ';'], \false, \false));
if ($parserState->comes(';')) {
$parserState->consume(';');
return new AtRuleStatement($identifier, $arguments, $identifierLineNumber);
}
$parserState->consume('{');
if (\substr_count($arguments, '(') !== \substr_count($arguments, ')')) {
if ($parserState->getSettings()->usesLenientParsing()) {
return null;
} else {
throw new SourceException('Unmatched brace count in media query', $parserState->currentLine());
}
}
$useRuleSet = \true;
foreach (AtRule::BLOCK_RULES as $blockRuleName) {
if (self::identifierIs($identifier, $blockRuleName)) {
$useRuleSet = \false;
break;
}
}
if ($useRuleSet) {
$atRule = new AtRuleSet($identifier, $arguments, $identifierLineNumber);
RuleSet::parseRuleSet($parserState, $atRule);
} else {
$atRule = new AtRuleBlockList($identifier, $arguments, $identifierLineNumber);
CSSList::parseList($parserState, $atRule);
if ($parserState->comes('}')) {
$parserState->consume('}');
}
}
return $atRule;
}
}
private static function identifierIs(string $identifier, string $match): bool
{
if (\strcasecmp($identifier, $match) === 0) {
return \true;
}
$matchResult = \preg_match("/^(-\\w+-)?{$match}\$/i", $identifier);
\assert(\is_int($matchResult));
return $matchResult === 1;
}
public function prepend(CSSListItem $item): void
{
\array_unshift($this->contents, $item);
}
public function append(CSSListItem $item): void
{
$this->contents[] = $item;
}
public function splice(int $offset, ?int $length = null, ?array $replacement = null): void
{
\array_splice($this->contents, $offset, $length, $replacement);
}
public function insertBefore(CSSListItem $item, CSSListItem $sibling): void
{
if (\in_array($sibling, $this->contents, \true)) {
$this->replace($sibling, [$item, $sibling]);
} else {
$this->append($item);
}
}
public function remove(CSSListItem $itemToRemove): bool
{
$key = \array_search($itemToRemove, $this->contents, \true);
if ($key !== \false) {
unset($this->contents[$key]);
return \true;
}
return \false;
}
public function replace(CSSListItem $oldItem, $newItem): bool
{
$key = \array_search($oldItem, $this->contents, \true);
if ($key !== \false) {
if (\is_array($newItem)) {
\array_splice($this->contents, $key, 1, $newItem);
} else {
\array_splice($this->contents, $key, 1, [$newItem]);
}
return \true;
}
return \false;
}
public function setContents(array $contents): void
{
$this->contents = [];
foreach ($contents as $content) {
$this->append($content);
}
}
public function removeDeclarationBlockBySelector($selectors, bool $removeAll = \false): void
{
if ($selectors instanceof DeclarationBlock) {
$selectors = $selectors->getSelectors();
}
if (!\is_array($selectors)) {
$selectors = \explode(',', $selectors);
}
foreach ($selectors as &$selector) {
if (!$selector instanceof Selector) {
if (!Selector::isValid($selector)) {
throw new UnexpectedTokenException("Selector did not match '" . Selector::SELECTOR_VALIDATION_RX . "'.", $selector, 'custom');
}
$selector = new Selector($selector);
}
}
foreach ($this->contents as $key => $item) {
if (!$item instanceof DeclarationBlock) {
continue;
}
if (self::selectorsMatch($item->getSelectors(), $selectors)) {
unset($this->contents[$key]);
if (!$removeAll) {
return;
}
}
}
}
protected function renderListContents(OutputFormat $outputFormat): string
{
$result = '';
$isFirst = \true;
$nextLevelFormat = $outputFormat;
if (!$this->isRootList()) {
$nextLevelFormat = $outputFormat->nextLevel();
}
$nextLevelFormatter = $nextLevelFormat->getFormatter();
$formatter = $outputFormat->getFormatter();
foreach ($this->contents as $listItem) {
$renderedCss = $formatter->safely(static function () use ($nextLevelFormat, $listItem): string {
return $listItem->render($nextLevelFormat);
});
if ($renderedCss === null) {
continue;
}
if ($isFirst) {
$isFirst = \false;
$result .= $nextLevelFormatter->spaceBeforeBlocks();
} else {
$result .= $nextLevelFormatter->spaceBetweenBlocks();
}
$result .= $renderedCss;
}
if (!$isFirst) {
$result .= $formatter->spaceAfterBlocks();
}
return $result;
}
abstract public function isRootList(): bool;
public function getContents(): array
{
return $this->contents;
}
public function getArrayRepresentation(): array
{
throw new \BadMethodCallException('`getArrayRepresentation` is not yet implemented for `' . self::class . '`');
}
private static function selectorsMatch(array $selectors1, array $selectors2): bool
{
$selectorStrings1 = self::getSelectorStrings($selectors1);
$selectorStrings2 = self::getSelectorStrings($selectors2);
\sort($selectorStrings1);
\sort($selectorStrings2);
return $selectorStrings1 === $selectorStrings2;
}
private static function getSelectorStrings(array $selectors): array
{
return \array_map(static function (Selector $selector): string {
return $selector->getSelector();
}, $selectors);
}
}
