<?php
declare (strict_types=1);
namespace MailPoetVendor\Sabberworm\CSS\RuleSet;
if (!defined('ABSPATH')) exit;
use MailPoetVendor\Sabberworm\CSS\Comment\Comment;
use MailPoetVendor\Sabberworm\CSS\Comment\CommentContainer;
use MailPoetVendor\Sabberworm\CSS\CSSElement;
use MailPoetVendor\Sabberworm\CSS\CSSList\CSSList;
use MailPoetVendor\Sabberworm\CSS\CSSList\CSSListItem;
use MailPoetVendor\Sabberworm\CSS\CSSList\KeyFrame;
use MailPoetVendor\Sabberworm\CSS\OutputFormat;
use MailPoetVendor\Sabberworm\CSS\Parsing\OutputException;
use MailPoetVendor\Sabberworm\CSS\Parsing\ParserState;
use MailPoetVendor\Sabberworm\CSS\Parsing\UnexpectedEOFException;
use MailPoetVendor\Sabberworm\CSS\Parsing\UnexpectedTokenException;
use MailPoetVendor\Sabberworm\CSS\Position\Position;
use MailPoetVendor\Sabberworm\CSS\Position\Positionable;
use MailPoetVendor\Sabberworm\CSS\Property\Declaration;
use MailPoetVendor\Sabberworm\CSS\Property\KeyframeSelector;
use MailPoetVendor\Sabberworm\CSS\Property\Selector;
use MailPoetVendor\Sabberworm\CSS\Settings;
class DeclarationBlock implements CSSElement, CSSListItem, Positionable, DeclarationList
{
use CommentContainer;
use LegacyDeclarationListMethods;
use Position;
private $selectors = [];
private $ruleSet;
public function __construct(?int $lineNumber = null)
{
$this->ruleSet = new RuleSet($lineNumber);
$this->setPosition($lineNumber);
}
public static function parse(ParserState $parserState, ?CSSList $list = null): ?DeclarationBlock
{
$comments = [];
$result = new DeclarationBlock($parserState->currentLine());
try {
$selectors = self::parseSelectors($parserState, $list, $comments);
$result->setSelectors($selectors, $list);
if ($parserState->comes('{')) {
$parserState->consume(1);
}
} catch (UnexpectedTokenException $e) {
if ($parserState->getSettings()->usesLenientParsing()) {
if (!$parserState->consumeIfComes('}')) {
$parserState->consumeUntil(['}', ParserState::EOF], \false, \true);
}
return null;
} else {
throw $e;
}
}
$result->setComments($comments);
RuleSet::parseRuleSet($parserState, $result->getRuleSet());
return $result;
}
public function setSelectors($selectors, ?CSSList $list = null): void
{
if (\is_array($selectors)) {
$selectorsToSet = $selectors;
} else {
try {
$parserState = new ParserState($selectors, Settings::create());
$selectorsToSet = self::parseSelectors($parserState, $list);
if (!$parserState->isEnd()) {
throw new UnexpectedTokenException('EOF', 'more');
}
} catch (UnexpectedTokenException $exception) {
throw new UnexpectedTokenException('Selector(s) string is not valid.', $selectors, 'custom');
}
}
foreach ($selectorsToSet as $key => $selector) {
if (!$selector instanceof Selector) {
if ($list === null || !$list instanceof KeyFrame) {
if (!Selector::isValid($selector)) {
throw new UnexpectedTokenException("Selector did not match '" . Selector::SELECTOR_VALIDATION_RX . "'.", $selector, 'custom');
}
$selectorsToSet[$key] = new Selector($selector);
} else {
if (!KeyframeSelector::isValid($selector)) {
throw new UnexpectedTokenException("Selector did not match '" . KeyframeSelector::SELECTOR_VALIDATION_RX . "'.", $selector, 'custom');
}
$selectorsToSet[$key] = new KeyframeSelector($selector);
}
}
}
$this->selectors = \array_values($selectorsToSet);
}
public function removeSelector($selectorToRemove): bool
{
if ($selectorToRemove instanceof Selector) {
$selectorToRemove = $selectorToRemove->getSelector();
}
foreach ($this->selectors as $key => $selector) {
if ($selector->getSelector() === $selectorToRemove) {
unset($this->selectors[$key]);
return \true;
}
}
return \false;
}
public function getSelectors(): array
{
return $this->selectors;
}
public function getRuleSet(): RuleSet
{
return $this->ruleSet;
}
public function addDeclaration(Declaration $declarationToAdd, ?Declaration $sibling = null): void
{
$this->ruleSet->addDeclaration($declarationToAdd, $sibling);
}
public function getDeclarations(?string $searchPattern = null): array
{
return $this->ruleSet->getDeclarations($searchPattern);
}
public function setDeclarations(array $declarations): void
{
$this->ruleSet->setDeclarations($declarations);
}
public function getDeclarationsAssociative(?string $searchPattern = null): array
{
return $this->ruleSet->getDeclarationsAssociative($searchPattern);
}
public function removeDeclaration(Declaration $declarationToRemove): void
{
$this->ruleSet->removeDeclaration($declarationToRemove);
}
public function removeMatchingDeclarations(string $searchPattern): void
{
$this->ruleSet->removeMatchingDeclarations($searchPattern);
}
public function removeAllDeclarations(): void
{
$this->ruleSet->removeAllDeclarations();
}
public function render(OutputFormat $outputFormat): string
{
$formatter = $outputFormat->getFormatter();
$result = $formatter->comments($this);
if (\count($this->selectors) === 0) {
throw new OutputException('Attempt to print declaration block with missing selector', $this->getLineNumber());
}
$result .= $outputFormat->getContentBeforeDeclarationBlock();
$result .= $formatter->implode($formatter->spaceBeforeSelectorSeparator() . ',' . $formatter->spaceAfterSelectorSeparator(), $this->selectors);
$result .= $outputFormat->getContentAfterDeclarationBlockSelectors();
$result .= $formatter->spaceBeforeOpeningBrace() . '{';
$result .= $this->ruleSet->render($outputFormat);
$result .= '}';
$result .= $outputFormat->getContentAfterDeclarationBlock();
return $result;
}
public function getArrayRepresentation(): array
{
throw new \BadMethodCallException('`getArrayRepresentation` is not yet implemented for `' . self::class . '`');
}
private static function parseSelectors(ParserState $parserState, ?CSSList $list, array &$comments = []): array
{
$selectorClass = $list instanceof KeyFrame ? KeyFrameSelector::class : Selector::class;
$selectors = [];
while (\true) {
$selectors[] = $selectorClass::parse($parserState, $comments);
if (!$parserState->consumeIfComes(',')) {
break;
}
}
return $selectors;
}
}
