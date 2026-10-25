<?php
declare (strict_types=1);
namespace MailPoetVendor\Sabberworm\CSS\Value;
if (!defined('ABSPATH')) exit;
use MailPoetVendor\Sabberworm\CSS\OutputFormat;
use MailPoetVendor\Sabberworm\CSS\Parsing\ParserState;
use MailPoetVendor\Sabberworm\CSS\Parsing\UnexpectedEOFException;
use MailPoetVendor\Sabberworm\CSS\Parsing\UnexpectedTokenException;
use MailPoetVendor\Sabberworm\CSS\ShortClassNameProvider;
class Size extends PrimitiveValue
{
use ShortClassNameProvider;
private const ABSOLUTE_SIZE_UNITS = ['px', 'pt', 'pc', 'cm', 'mm', 'mozmm', 'in', 'vh', 'dvh', 'svh', 'lvh', 'vw', 'vmin', 'vmax', 'rem'];
private const RELATIVE_SIZE_UNITS = ['%', 'em', 'ex', 'ch', 'fr'];
private const NON_SIZE_UNITS = ['deg', 'grad', 'rad', 's', 'ms', 'turn', 'Hz', 'kHz'];
private static $SIZE_UNITS = null;
private $size;
private $unit;
private $isColorComponent;
public function __construct($size, ?string $unit = null, bool $isColorComponent = \false, ?int $lineNumber = null)
{
parent::__construct($lineNumber);
$this->size = (float) $size;
$this->unit = $unit;
$this->isColorComponent = $isColorComponent;
}
public static function parse(ParserState $parserState, bool $isColorComponent = \false): Size
{
$size = '';
if ($parserState->comes('-')) {
$size .= $parserState->consume('-');
}
while (\is_numeric($parserState->peek()) || $parserState->comes('.') || $parserState->comes('e', \true)) {
if ($parserState->comes('.')) {
$size .= $parserState->consume('.');
} elseif ($parserState->comes('e', \true)) {
$lookahead = $parserState->peek(1, 1);
if (\is_numeric($lookahead) || $lookahead === '+' || $lookahead === '-') {
$size .= $parserState->consume(2);
} else {
break;
}
} else {
$size .= $parserState->consume(1);
}
}
$unit = null;
$sizeUnits = self::getSizeUnits();
foreach ($sizeUnits as $length => &$values) {
$key = \strtolower($parserState->peek($length));
if (\array_key_exists($key, $values)) {
if (($unit = $values[$key]) !== null) {
$parserState->consume($length);
break;
}
}
}
return new Size((float) $size, $unit, $isColorComponent, $parserState->currentLine());
}
private static function getSizeUnits(): array
{
if (!\is_array(self::$SIZE_UNITS)) {
self::$SIZE_UNITS = [];
$sizeUnits = \array_merge(self::ABSOLUTE_SIZE_UNITS, self::RELATIVE_SIZE_UNITS, self::NON_SIZE_UNITS);
foreach ($sizeUnits as $sizeUnit) {
$tokenLength = \strlen($sizeUnit);
if (!isset(self::$SIZE_UNITS[$tokenLength])) {
self::$SIZE_UNITS[$tokenLength] = [];
}
self::$SIZE_UNITS[$tokenLength][\strtolower($sizeUnit)] = $sizeUnit;
}
\krsort(self::$SIZE_UNITS, \SORT_NUMERIC);
}
return self::$SIZE_UNITS;
}
public function setUnit(string $unit): void
{
$this->unit = $unit;
}
public function getUnit(): ?string
{
return $this->unit;
}
public function setSize($size): void
{
$this->size = (float) $size;
}
public function getSize(): float
{
return $this->size;
}
public function isColorComponent(): bool
{
return $this->isColorComponent;
}
public function isSize(): bool
{
if (\in_array($this->unit, self::NON_SIZE_UNITS, \true)) {
return \false;
}
return !$this->isColorComponent();
}
public function isRelative(): bool
{
if (\in_array($this->unit, self::RELATIVE_SIZE_UNITS, \true)) {
return \true;
}
if ($this->unit === null && $this->size !== 0.0) {
return \true;
}
return \false;
}
public function render(OutputFormat $outputFormat): string
{
$locale = \localeconv();
$decimalPoint = \preg_quote($locale['decimal_point'], '/');
$matchResult = \preg_match('/[\d\.]+e[+-]?\d+/i', (string) $this->size);
\assert(\is_int($matchResult));
if ($matchResult === 1) {
$size = \preg_replace("/{$decimalPoint}?0+\$/", '', \sprintf('%f', $this->size));
\assert(\is_string($size));
} else {
$size = (string) $this->size;
}
$renderedSize = \preg_replace(["/{$decimalPoint}/", '/^(-?)0\./'], ['.', '$1.'], $size);
\assert(\is_string($renderedSize));
return $renderedSize . ($this->unit ?? '');
}
public function getArrayRepresentation(): array
{
return [
'class' => $this->getShortClassName(),
'number' => $this->size,
'unit' => $this->unit,
];
}
}
