<?php
declare (strict_types=1);
namespace MailPoetVendor\Pelago\Emogrifier;
if (!defined('ABSPATH')) exit;
use MailPoetVendor\Pelago\Emogrifier\Css\CssDocument;
use MailPoetVendor\Pelago\Emogrifier\HtmlProcessor\AbstractHtmlProcessor;
use MailPoetVendor\Pelago\Emogrifier\Utilities\CssConcatenator;
use MailPoetVendor\Pelago\Emogrifier\Utilities\DeclarationBlockParser;
use MailPoetVendor\Pelago\Emogrifier\Utilities\Preg;
use MailPoetVendor\Symfony\Component\CssSelector\CssSelectorConverter;
use MailPoetVendor\Symfony\Component\CssSelector\Exception\ParseException;
final class CssInliner extends AbstractHtmlProcessor
{
private const CACHE_KEY_SELECTOR = 0;
private const CACHE_KEY_COMBINED_STYLES = 1;
private const PSEUDO_CLASS_MATCHER = 'empty|(?:first|last|nth(?:-last)?+|only)-(?:child|of-type)|not\([[:ascii:]]*\)|root';
private const OF_TYPE_PSEUDO_CLASS_MATCHER = '(?:first|last|nth(?:-last)?+|only)-of-type';
private const COMBINATOR_MATCHER = '(?:\s++|\s*+[>+~]\s*+)(?=[[:alpha:]_\-.#*:\[])';
private const QSA_ALWAYS_THROW_PARSE_EXCEPTION = 'alwaysThrowParseException';
private $excludedSelectors = [];
private $excludedCssSelectors = [];
private $allowedMediaTypes = ['all' => \true, 'screen' => \true, 'print' => \true];
private $caches = [self::CACHE_KEY_SELECTOR => [], self::CACHE_KEY_COMBINED_STYLES => []];
private $cssSelectorConverter = null;
private $visitedNodes = [];
private $styleAttributesForNodes = [];
private $isInlineStyleAttributesParsingEnabled = \true;
private $isStyleBlocksParsingEnabled = \true;
private $selectorPrecedenceMatchers = [
'\#' => 10000,
'(?:\.|\[|(?<!:):(?!not\())' => 100,
'(?:(?<![="\':\w\-])|::)' => 1,
];
private $matchingUninlinableCssRules = null;
private $debug = \false;
public function inlineCss(string $css = ''): self
{
$this->clearAllCaches();
$this->purgeVisitedNodes();
$this->normalizeStyleAttributesOfAllNodes();
$combinedCss = $css;
if ($this->isStyleBlocksParsingEnabled) {
$combinedCss .= $this->getCssFromAllStyleNodes();
}
$parsedCss = new CssDocument($combinedCss, $this->debug);
$excludedNodes = $this->getNodesToExclude();
$cssRules = $this->collateCssRules($parsedCss);
foreach ($cssRules['inlinable'] as $cssRule) {
foreach ($this->querySelectorAll($cssRule['selector']) as $node) {
if (\in_array($node, $excludedNodes, \true)) {
continue;
}
$this->copyInlinableCssToStyleAttribute($node, $cssRule);
}
}
if ($this->isInlineStyleAttributesParsingEnabled) {
$this->fillStyleAttributesWithMergedStyles();
}
$this->removeImportantAnnotationFromAllInlineStyles();
$this->determineMatchingUninlinableCssRules($cssRules['uninlinable']);
$this->copyUninlinableCssToStyleNode($parsedCss);
return $this;
}
public function disableInlineStyleAttributesParsing(): self
{
$this->isInlineStyleAttributesParsingEnabled = \false;
return $this;
}
public function disableStyleBlocksParsing(): self
{
$this->isStyleBlocksParsingEnabled = \false;
return $this;
}
public function addAllowedMediaType(string $mediaName): self
{
$this->allowedMediaTypes[$mediaName] = \true;
return $this;
}
public function removeAllowedMediaType(string $mediaName): self
{
if (isset($this->allowedMediaTypes[$mediaName])) {
unset($this->allowedMediaTypes[$mediaName]);
}
return $this;
}
public function addExcludedSelector(string $selector): self
{
$this->excludedSelectors[$selector] = \true;
return $this;
}
public function removeExcludedSelector(string $selector): self
{
if (isset($this->excludedSelectors[$selector])) {
unset($this->excludedSelectors[$selector]);
}
return $this;
}
public function addExcludedCssSelector(string $selector): self
{
$this->excludedCssSelectors[$selector] = \true;
return $this;
}
public function removeExcludedCssSelector(string $selector): self
{
if (isset($this->excludedCssSelectors[$selector])) {
unset($this->excludedCssSelectors[$selector]);
}
return $this;
}
public function setDebug(bool $debug): self
{
$this->debug = $debug;
return $this;
}
public function getMatchingUninlinableSelectors(): array
{
return \array_column($this->getMatchingUninlinableCssRules(), 'selector');
}
private function getMatchingUninlinableCssRules(): array
{
if (!\is_array($this->matchingUninlinableCssRules)) {
throw new \BadMethodCallException('inlineCss must be called first', 1568385221);
}
return $this->matchingUninlinableCssRules;
}
private function clearAllCaches(): void
{
$this->caches = [self::CACHE_KEY_SELECTOR => [], self::CACHE_KEY_COMBINED_STYLES => []];
DeclarationBlockParser::clearCache();
}
private function purgeVisitedNodes(): void
{
$this->visitedNodes = [];
$this->styleAttributesForNodes = [];
}
private function normalizeStyleAttributesOfAllNodes(): void
{
foreach ($this->getAllNodesWithStyleAttribute() as $node) {
if ($this->isInlineStyleAttributesParsingEnabled) {
$this->normalizeStyleAttributes($node);
}
$node->removeAttribute('style');
}
}
private function getAllNodesWithStyleAttribute(): \DOMNodeList
{
$query = '//*[@style]';
$matches = $this->xPath->query($query);
\assert($matches instanceof \DOMNodeList);
return $matches;
}
private function normalizeStyleAttributes(\DOMElement $node): void
{
$pattern = '/-{0,2}+[_a-zA-Z][\w\-]*+(?=:)/S';
$callback = \Closure::fromCallable([self::class, 'normalizePropertyNameCallback']);
$normalizedOriginalStyle = (new Preg())->throwExceptions($this->debug)->replaceCallback($pattern, $callback, $node->getAttribute('style'));
$nodePath = $node->getNodePath();
if (\is_string($nodePath) && $nodePath !== '' && !isset($this->styleAttributesForNodes[$nodePath])) {
$this->styleAttributesForNodes[$nodePath] = DeclarationBlockParser::parse($normalizedOriginalStyle);
$this->visitedNodes[$nodePath] = $node;
}
$node->setAttribute('style', $normalizedOriginalStyle);
}
private static function normalizePropertyNameCallback(array $matches): string
{
return DeclarationBlockParser::normalizePropertyName($matches[0]);
}
private function getCssFromAllStyleNodes(): string
{
$styleNodes = $this->xPath->query('//style');
if ($styleNodes === \false) {
return '';
}
$css = '';
foreach ($styleNodes as $styleNode) {
\assert($styleNode instanceof \DOMNode);
if (\is_string($styleNode->nodeValue)) {
$css .= "\n\n" . $styleNode->nodeValue;
}
$parentNode = $styleNode->parentNode;
if ($parentNode instanceof \DOMNode) {
$parentNode->removeChild($styleNode);
}
}
return $css;
}
private function getNodesToExclude(): array
{
$excludedNodes = [];
foreach (\array_keys($this->excludedSelectors) as $selectorToExclude) {
\array_push($excludedNodes, ...$this->querySelectorAll($selectorToExclude));
}
return $excludedNodes;
}
private function querySelectorAll(string $selectors, array $options = []): \DOMNodeList
{
try {
$result = $this->xPath->query($this->getCssSelectorConverter()->toXPath($selectors));
\assert($result instanceof \DOMNodeList);
} catch (ParseException $exception) {
$alwaysThrowParseException = $options[self::QSA_ALWAYS_THROW_PARSE_EXCEPTION] ?? \false;
if ($this->debug || $alwaysThrowParseException) {
throw $exception;
}
$result = new \DOMNodeList();
}
return $result;
}
private function getCssSelectorConverter(): CssSelectorConverter
{
if (!$this->cssSelectorConverter instanceof CssSelectorConverter) {
$this->cssSelectorConverter = new CssSelectorConverter();
}
return $this->cssSelectorConverter;
}
private function collateCssRules(CssDocument $parsedCss): array
{
$matches = $parsedCss->getStyleRulesData(\array_keys($this->allowedMediaTypes));
$preg = (new Preg())->throwExceptions($this->debug);
$cssRules = ['inlinable' => [], 'uninlinable' => []];
foreach ($matches as $key => $cssRule) {
if (!$cssRule->hasAtLeastOneDeclaration()) {
continue;
}
$mediaQuery = $cssRule->getContainingAtRule();
$declarationsBlock = $cssRule->getDeclarationsAsText();
$selectors = $cssRule->getSelectors();
if (\count($this->excludedCssSelectors) > 0) {
$selectorsNormalized = \array_map(static function (string $selector) use ($preg): string {
return $preg->replace('@\s++@u', ' ', $selector);
}, $selectors);
$selectors = \array_filter($selectorsNormalized, function (string $selector): bool {
return !isset($this->excludedCssSelectors[$selector]);
});
}
foreach ($selectors as $selector) {
$hasPseudoElement = \strpos($selector, '::') !== \false;
$hasUnmatchablePseudo = $hasPseudoElement || $this->hasUnsupportedPseudoClass($selector);
$parsedCssRule = [
'media' => $mediaQuery,
'selector' => $selector,
'hasUnmatchablePseudo' => $hasUnmatchablePseudo,
'declarationsBlock' => $declarationsBlock,
'line' => $key,
];
$ruleType = !$cssRule->hasContainingAtRule() && !$hasUnmatchablePseudo ? 'inlinable' : 'uninlinable';
$cssRules[$ruleType][] = $parsedCssRule;
}
}
\usort(
$cssRules['inlinable'],
function (array $first, array $second): int {
return $this->sortBySelectorPrecedence($first, $second);
}
);
return $cssRules;
}
private function hasUnsupportedPseudoClass(string $selector): bool
{
$preg = (new Preg())->throwExceptions($this->debug);
if ($preg->match('/:(?!' . self::PSEUDO_CLASS_MATCHER . ')[\w\-]/i', $selector) !== 0) {
return \true;
}
if ($preg->match('/:(?:' . self::OF_TYPE_PSEUDO_CLASS_MATCHER . ')/i', $selector) === 0) {
return \false;
}
foreach ($preg->split('/' . self::COMBINATOR_MATCHER . '/', $selector) as $selectorPart) {
if ($this->selectorPartHasUnsupportedOfTypePseudoClass($selectorPart)) {
return \true;
}
}
return \false;
}
private function selectorPartHasUnsupportedOfTypePseudoClass(string $selectorPart): bool
{
$preg = (new Preg())->throwExceptions($this->debug);
if ($preg->match('/^[\w\-]/', $selectorPart) !== 0) {
return \false;
}
return $preg->match('/:(?:' . self::OF_TYPE_PSEUDO_CLASS_MATCHER . ')/i', $selectorPart) !== 0;
}
private function sortBySelectorPrecedence(array $first, array $second): int
{
$precedenceOfFirst = $this->getCssSelectorPrecedence($first['selector']);
$precedenceOfSecond = $this->getCssSelectorPrecedence($second['selector']);
$precedenceForEquals = $first['line'] < $second['line'] ? -1 : 1;
$precedenceForNotEquals = $precedenceOfFirst < $precedenceOfSecond ? -1 : 1;
return $precedenceOfFirst === $precedenceOfSecond ? $precedenceForEquals : $precedenceForNotEquals;
}
private function getCssSelectorPrecedence(string $selector): int
{
$selectorKey = $selector;
if (isset($this->caches[self::CACHE_KEY_SELECTOR][$selectorKey])) {
return $this->caches[self::CACHE_KEY_SELECTOR][$selectorKey];
}
$preg = (new Preg())->throwExceptions($this->debug);
$precedence = 0;
foreach ($this->selectorPrecedenceMatchers as $matcher => $value) {
if (\trim($selector) === '') {
break;
}
$count = 0;
$selector = $preg->replace('/' . $matcher . '\w+/', '', $selector, -1, $count);
$precedence += $value * $count;
}
$this->caches[self::CACHE_KEY_SELECTOR][$selectorKey] = $precedence;
return $precedence;
}
private function copyInlinableCssToStyleAttribute(\DOMElement $node, array $cssRule): void
{
$declarationsBlock = $cssRule['declarationsBlock'];
$newStyleDeclarations = DeclarationBlockParser::parse($declarationsBlock);
if ($newStyleDeclarations === []) {
return;
}
if ($node->hasAttribute('style')) {
$oldStyleDeclarations = DeclarationBlockParser::parse($node->getAttribute('style'));
} else {
$oldStyleDeclarations = [];
}
$node->setAttribute('style', $this->generateStyleStringFromDeclarationsArrays($oldStyleDeclarations, $newStyleDeclarations));
}
private function generateStyleStringFromDeclarationsArrays(array $oldStyles, array $newStyles): string
{
$cacheKey = \serialize([$oldStyles, $newStyles]);
\assert($cacheKey !== '');
if (isset($this->caches[self::CACHE_KEY_COMBINED_STYLES][$cacheKey])) {
return $this->caches[self::CACHE_KEY_COMBINED_STYLES][$cacheKey];
}
foreach ($oldStyles as $attributeName => $attributeValue) {
if (!isset($newStyles[$attributeName])) {
continue;
}
$newAttributeValue = $newStyles[$attributeName];
if ($this->attributeValueIsImportant($attributeValue) && !$this->attributeValueIsImportant($newAttributeValue)) {
unset($newStyles[$attributeName]);
} else {
unset($oldStyles[$attributeName]);
}
}
$combinedStyles = \array_merge($oldStyles, $newStyles);
$style = '';
foreach ($combinedStyles as $attributeName => $attributeValue) {
$trimmedAttributeName = \trim($attributeName);
if ($trimmedAttributeName === '') {
throw new \UnexpectedValueException('An empty property name was encountered.', 1727046078);
}
$propertyName = DeclarationBlockParser::normalizePropertyName($trimmedAttributeName);
$propertyValue = \trim($attributeValue);
$style .= $propertyName . ': ' . $propertyValue . '; ';
}
$trimmedStyle = \rtrim($style);
$this->caches[self::CACHE_KEY_COMBINED_STYLES][$cacheKey] = $trimmedStyle;
return $trimmedStyle;
}
private function attributeValueIsImportant(string $attributeValue): bool
{
return (new Preg())->throwExceptions($this->debug)->match('/!\s*+important$/i', $attributeValue) !== 0;
}
private function fillStyleAttributesWithMergedStyles(): void
{
foreach ($this->styleAttributesForNodes as $nodePath => $styleAttributesForNode) {
$node = $this->visitedNodes[$nodePath];
$currentStyleAttributes = DeclarationBlockParser::parse($node->getAttribute('style'));
$node->setAttribute('style', $this->generateStyleStringFromDeclarationsArrays($currentStyleAttributes, $styleAttributesForNode));
}
}
private function removeImportantAnnotationFromAllInlineStyles(): void
{
foreach ($this->getAllNodesWithStyleAttribute() as $node) {
$this->removeImportantAnnotationFromNodeInlineStyle($node);
}
}
private function removeImportantAnnotationFromNodeInlineStyle(\DOMElement $node): void
{
$style = $node->getAttribute('style');
$inlineStyleDeclarations = DeclarationBlockParser::parse((bool) $style ? $style : '');
$regularStyleDeclarations = [];
$importantStyleDeclarations = [];
$preg = (new Preg())->throwExceptions($this->debug);
foreach ($inlineStyleDeclarations as $property => $value) {
if ($this->attributeValueIsImportant($value)) {
$declaration = $preg->replace('/\s*+!\s*+important$/i', '', $value);
$importantStyleDeclarations[$property] = $declaration;
} else {
$regularStyleDeclarations[$property] = $value;
}
}
$inlineStyleDeclarationsInNewOrder = \array_merge($regularStyleDeclarations, $importantStyleDeclarations);
$node->setAttribute('style', $this->generateStyleStringFromSingleDeclarationsArray($inlineStyleDeclarationsInNewOrder));
}
private function generateStyleStringFromSingleDeclarationsArray(array $styleDeclarations): string
{
return $this->generateStyleStringFromDeclarationsArrays([], $styleDeclarations);
}
private function determineMatchingUninlinableCssRules(array $cssRules): void
{
$this->matchingUninlinableCssRules = \array_filter($cssRules, function (array $cssRule): bool {
return $this->existsMatchForSelectorInCssRule($cssRule);
});
}
private function existsMatchForSelectorInCssRule(array $cssRule): bool
{
$selector = $cssRule['selector'];
if ($cssRule['hasUnmatchablePseudo']) {
$selector = $this->removeUnmatchablePseudoComponents($selector);
}
return $this->existsMatchForCssSelector($selector);
}
private function existsMatchForCssSelector(string $cssSelector): bool
{
try {
$nodesMatchingSelector = $this->querySelectorAll($cssSelector, [self::QSA_ALWAYS_THROW_PARSE_EXCEPTION => \true]);
} catch (ParseException $e) {
if ($this->debug) {
throw $e;
}
return \true;
}
return $nodesMatchingSelector->length !== 0;
}
private function removeUnmatchablePseudoComponents(string $selector): string
{
$preg = (new Preg())->throwExceptions($this->debug);
$pattern = '/([\s>+~]?+):not(\([^()]*+(?:(?2)[^()]*+)*+\))/i';
$callback = \Closure::fromCallable([$this, 'replaceUnmatchableNotComponent']);
$untrimmedSelectorWithoutNots = $preg->replaceCallback($pattern, $callback, ' ' . $selector);
$selectorWithoutNots = \ltrim($untrimmedSelectorWithoutNots);
$selectorWithoutUnmatchablePseudoComponents = $this->removeSelectorComponents(':(?!' . self::PSEUDO_CLASS_MATCHER . '):?+[\w\-]++(?:\([^\)]*+\))?+', $selectorWithoutNots);
if ($preg->match('/:(?:' . self::OF_TYPE_PSEUDO_CLASS_MATCHER . ')/i', $selectorWithoutUnmatchablePseudoComponents) === 0) {
return $selectorWithoutUnmatchablePseudoComponents;
}
$selectorParts = $preg->split('/(' . self::COMBINATOR_MATCHER . ')/', $selectorWithoutUnmatchablePseudoComponents, -1, \PREG_SPLIT_DELIM_CAPTURE | \PREG_SPLIT_NO_EMPTY);
return \implode('', \array_map(function (string $selectorPart): string {
return $this->removeUnsupportedOfTypePseudoClasses($selectorPart);
}, $selectorParts));
}
private function replaceUnmatchableNotComponent(array $matches): string
{
[$notComponentWithAnyPrecedingCombinator, $anyPrecedingCombinator, $notArgumentInBrackets] = $matches;
if ($this->hasUnsupportedPseudoClass($notArgumentInBrackets)) {
return $anyPrecedingCombinator !== '' ? $anyPrecedingCombinator . '*' : '';
}
return $notComponentWithAnyPrecedingCombinator;
}
private function removeSelectorComponents(string $matcher, string $selector): string
{
return (new Preg())->throwExceptions($this->debug)->replace(['/([\s>+~]|^)' . $matcher . '/i', '/' . $matcher . '/i'], ['$1*', ''], $selector);
}
private function removeUnsupportedOfTypePseudoClasses(string $selectorPart): string
{
if (!$this->selectorPartHasUnsupportedOfTypePseudoClass($selectorPart)) {
return $selectorPart;
}
return $this->removeSelectorComponents(':(?:' . self::OF_TYPE_PSEUDO_CLASS_MATCHER . ')(?:\([^\)]*+\))?+', $selectorPart);
}
private function copyUninlinableCssToStyleNode(CssDocument $parsedCss): void
{
$css = $parsedCss->renderNonConditionalAtRules();
if ($this->getMatchingUninlinableCssRules() !== []) {
$cssConcatenator = new CssConcatenator();
foreach ($this->getMatchingUninlinableCssRules() as $cssRule) {
$cssConcatenator->append([$cssRule['selector']], $cssRule['declarationsBlock'], $cssRule['media']);
}
$css .= $cssConcatenator->getCss();
}
if ($css !== '') {
$this->addStyleElementToDocument($css);
}
}
protected function addStyleElementToDocument(string $css): void
{
$domDocument = $this->getDomDocument();
$styleElement = $domDocument->createElement('style', $css);
$styleAttribute = $domDocument->createAttribute('type');
$styleAttribute->value = 'text/css';
$styleElement->appendChild($styleAttribute);
$headElement = $this->getHeadElement();
$headElement->appendChild($styleElement);
}
private function getHeadElement(): \DOMElement
{
$node = $this->getDomDocument()->getElementsByTagName('head')->item(0);
\assert($node instanceof \DOMElement);
return $node;
}
}
