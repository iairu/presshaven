<?php
declare (strict_types=1);
namespace MailPoetVendor\Sabberworm\CSS\Value;
if (!defined('ABSPATH')) exit;
use MailPoetVendor\Sabberworm\CSS\OutputFormat;
use MailPoetVendor\Sabberworm\CSS\Parsing\ParserState;
use MailPoetVendor\Sabberworm\CSS\Parsing\UnexpectedEOFException;
use MailPoetVendor\Sabberworm\CSS\Parsing\UnexpectedTokenException;
class Color extends CSSFunction
{
public function __construct(array $colorValues, ?int $lineNumber = null)
{
parent::__construct(\implode('', \array_keys($colorValues)), $colorValues, ',', $lineNumber);
}
public static function parse(ParserState $parserState, bool $ignoreCase = \false): CSSFunction
{
return $parserState->comes('#') ? self::parseHexColor($parserState) : self::parseColorFunction($parserState);
}
private static function parseHexColor(ParserState $parserState): Color
{
$parserState->consume('#');
$hexValue = $parserState->parseIdentifier(\false);
if ($parserState->strlen($hexValue) === 3) {
$hexValue = $hexValue[0] . $hexValue[0] . $hexValue[1] . $hexValue[1] . $hexValue[2] . $hexValue[2];
} elseif ($parserState->strlen($hexValue) === 4) {
$hexValue = $hexValue[0] . $hexValue[0] . $hexValue[1] . $hexValue[1] . $hexValue[2] . $hexValue[2] . $hexValue[3] . $hexValue[3];
}
if ($parserState->strlen($hexValue) === 8) {
$colorValues = ['r' => new Size(\intval($hexValue[0] . $hexValue[1], 16), null, \true, $parserState->currentLine()), 'g' => new Size(\intval($hexValue[2] . $hexValue[3], 16), null, \true, $parserState->currentLine()), 'b' => new Size(\intval($hexValue[4] . $hexValue[5], 16), null, \true, $parserState->currentLine()), 'a' => new Size(\round(self::mapRange(\intval($hexValue[6] . $hexValue[7], 16), 0, 255, 0, 1), 2), null, \true, $parserState->currentLine())];
} elseif ($parserState->strlen($hexValue) === 6) {
$colorValues = ['r' => new Size(\intval($hexValue[0] . $hexValue[1], 16), null, \true, $parserState->currentLine()), 'g' => new Size(\intval($hexValue[2] . $hexValue[3], 16), null, \true, $parserState->currentLine()), 'b' => new Size(\intval($hexValue[4] . $hexValue[5], 16), null, \true, $parserState->currentLine())];
} else {
throw new UnexpectedTokenException('Invalid hex color value', $hexValue, 'custom', $parserState->currentLine());
}
return new Color($colorValues, $parserState->currentLine());
}
private static function parseColorFunction(ParserState $parserState): CSSFunction
{
$colorValues = [];
$colorMode = $parserState->parseIdentifier(\true);
$parserState->consumeWhiteSpace();
$parserState->consume('(');
switch ($colorMode) {
case 'rgb':
$colorModeForParsing = 'rgba';
$mayHaveOptionalAlpha = \true;
break;
case 'hsl':
$colorModeForParsing = 'hsla';
$mayHaveOptionalAlpha = \true;
break;
case 'rgba':
case 'hsla':
$colorModeForParsing = $colorMode;
$mayHaveOptionalAlpha = \true;
break;
default:
$colorModeForParsing = $colorMode;
$mayHaveOptionalAlpha = \false;
}
$containsVar = \false;
$containsNone = \false;
$isLegacySyntax = \false;
$expectedArgumentCount = $parserState->strlen($colorModeForParsing);
for ($argumentIndex = 0; $argumentIndex < $expectedArgumentCount; ++$argumentIndex) {
$parserState->consumeWhiteSpace();
$valueKey = $colorModeForParsing[$argumentIndex];
if ($parserState->comes('var')) {
$colorValues[$valueKey] = CSSFunction::parseIdentifierOrFunction($parserState);
$containsVar = \true;
} elseif (!$isLegacySyntax && $parserState->comes('none')) {
$colorValues[$valueKey] = $parserState->parseIdentifier();
$containsNone = \true;
} else {
$colorValues[$valueKey] = Size::parse($parserState, \true);
}
$parserState->consumeWhiteSpace();
$canCloseNow = $containsVar || $mayHaveOptionalAlpha && $argumentIndex >= $expectedArgumentCount - 2;
if ($canCloseNow && $parserState->comes(')')) {
break;
}
if ($argumentIndex === 0 && !$containsNone) {
if ($parserState->comes(')')) {
throw new UnexpectedTokenException('Color function with no arguments', '', 'custom', $parserState->currentLine());
}
$isLegacySyntax = $parserState->comes(',');
}
if ($isLegacySyntax && $argumentIndex < $expectedArgumentCount - 1) {
$parserState->consume(',');
}
if (!$isLegacySyntax) {
if ($containsVar) {
if ($parserState->comes('/')) {
$parserState->consume('/');
}
} elseif (($colorModeForParsing[$argumentIndex + 1] ?? '') === 'a') {
$parserState->consume('/');
}
}
}
$parserState->consume(')');
return $containsVar ? new CSSFunction($colorMode, \array_values($colorValues), ',', $parserState->currentLine()) : new Color($colorValues, $parserState->currentLine());
}
private static function mapRange(float $value, float $fromMin, float $fromMax, float $toMin, float $toMax): float
{
$fromRange = $fromMax - $fromMin;
$toRange = $toMax - $toMin;
$multiplier = $toRange / $fromRange;
$newValue = $value - $fromMin;
$newValue *= $multiplier;
return $newValue + $toMin;
}
public function getColor(): array
{
return $this->components;
}
public function setColor(array $colorValues): void
{
$this->setName(\implode('', \array_keys($colorValues)));
$this->components = $colorValues;
}
public function getColorDescription(): string
{
return $this->getName();
}
public function render(OutputFormat $outputFormat): string
{
if ($this->shouldRenderAsHex($outputFormat)) {
return $this->renderAsHex();
}
if ($this->shouldRenderInModernSyntax()) {
return $this->renderInModernSyntax($outputFormat);
}
return parent::render($outputFormat);
}
private function shouldRenderAsHex(OutputFormat $outputFormat): bool
{
return $outputFormat->usesRgbHashNotation() && $this->getRealName() === 'rgb' && $this->allComponentsAreNumbers();
}
private function getRealName(): string
{
return \implode('', \array_keys($this->components));
}
private function allComponentsAreNumbers(): bool
{
foreach ($this->components as $component) {
if (!$component instanceof Size || $component->getUnit() !== null) {
return \false;
}
}
return \true;
}
private function renderAsHex(): string
{
$result = \sprintf('%02x%02x%02x', $this->components['r']->getSize(), $this->components['g']->getSize(), $this->components['b']->getSize());
$canUseShortVariant = $result[0] === $result[1] && $result[2] === $result[3] && $result[4] === $result[5];
return '#' . ($canUseShortVariant ? $result[0] . $result[2] . $result[4] : $result);
}
private function shouldRenderInModernSyntax(): bool
{
if ($this->hasNoneAsComponentValue()) {
return \true;
}
if (!$this->colorFunctionMayHaveMixedValueTypes($this->getRealName())) {
return \false;
}
$hasPercentage = \false;
$hasNumber = \false;
foreach ($this->components as $key => $value) {
if ($key === 'a') {
break;
}
if (!$value instanceof Size) {
return \false;
}
$unit = $value->getUnit();
if ($unit === null) {
$hasNumber = \true;
} elseif ($unit === '%') {
$hasPercentage = \true;
} else {
return \false;
}
}
return $hasPercentage && $hasNumber;
}
private function hasNoneAsComponentValue(): bool
{
return \in_array('none', $this->components, \true);
}
private function colorFunctionMayHaveMixedValueTypes(string $function): bool
{
$functionsThatMayHaveMixedValueTypes = ['rgb', 'rgba'];
return \in_array($function, $functionsThatMayHaveMixedValueTypes, \true);
}
private function renderInModernSyntax(OutputFormat $outputFormat): string
{
$componentsWithoutAlpha = $this->components;
\end($componentsWithoutAlpha);
if (\key($componentsWithoutAlpha) === 'a') {
$alpha = $this->components['a'];
unset($componentsWithoutAlpha['a']);
}
$formatter = $outputFormat->getFormatter();
$arguments = $formatter->implode(' ', $componentsWithoutAlpha);
if (isset($alpha)) {
$separator = $formatter->spaceBeforeListArgumentSeparator('/') . '/' . $formatter->spaceAfterListArgumentSeparator('/');
$arguments = $formatter->implode($separator, [$arguments, $alpha]);
}
return $this->getName() . '(' . $arguments . ')';
}
}
