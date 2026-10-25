<?php
declare (strict_types=1);
namespace MailPoetVendor\Sabberworm\CSS\Value;
if (!defined('ABSPATH')) exit;
use MailPoetVendor\Sabberworm\CSS\CSSElement;
use MailPoetVendor\Sabberworm\CSS\Parsing\ParserState;
use MailPoetVendor\Sabberworm\CSS\Parsing\SourceException;
use MailPoetVendor\Sabberworm\CSS\Parsing\UnexpectedEOFException;
use MailPoetVendor\Sabberworm\CSS\Parsing\UnexpectedTokenException;
use MailPoetVendor\Sabberworm\CSS\Position\Position;
use MailPoetVendor\Sabberworm\CSS\Position\Positionable;
use MailPoetVendor\Sabberworm\CSS\ShortClassNameProvider;
abstract class Value implements CSSElement, Positionable
{
use Position;
use ShortClassNameProvider;
public function __construct(?int $lineNumber = null)
{
$this->setPosition($lineNumber);
}
public static function parseValue(ParserState $parserState, array $listDelimiters = [])
{
$stack = [];
$parserState->consumeWhiteSpace();
while (!($parserState->comes('}') || $parserState->comes(';') || $parserState->comes('!') || $parserState->comes(')') || $parserState->isEnd())) {
if (\count($stack) > 0) {
$foundDelimiter = \false;
foreach ($listDelimiters as $delimiter) {
if ($parserState->comes($delimiter)) {
\array_push($stack, $parserState->consume($delimiter));
$parserState->consumeWhiteSpace();
$foundDelimiter = \true;
break;
}
}
if (!$foundDelimiter) {
\array_push($stack, ' ');
}
}
\array_push($stack, self::parsePrimitiveValue($parserState));
$parserState->consumeWhiteSpace();
}
foreach ($listDelimiters as $delimiter) {
$stackSize = \count($stack);
if ($stackSize === 1) {
return $stack[0];
}
$newStack = [];
for ($offset = 0; $offset < $stackSize; ++$offset) {
if ($offset === $stackSize - 1 || $delimiter !== $stack[$offset + 1]) {
$newStack[] = $stack[$offset];
continue;
}
$length = 2;
for ($i = $offset + 3; $i < $stackSize; $i += 2, ++$length) {
if ($delimiter !== $stack[$i]) {
break;
}
}
$list = new RuleValueList($delimiter, $parserState->currentLine());
for ($i = $offset; $i - $offset < $length * 2; $i += 2) {
$list->addListComponent($stack[$i]);
}
$newStack[] = $list;
$offset += $length * 2 - 2;
}
$stack = $newStack;
}
if (!isset($stack[0])) {
throw new UnexpectedTokenException(" {$parserState->peek()} ", $parserState->peek(1, -1) . $parserState->peek(2), 'literal', $parserState->currentLine());
}
return $stack[0];
}
public static function parseIdentifierOrFunction(ParserState $parserState, bool $ignoreCase = \false)
{
$anchor = $parserState->anchor();
$result = $parserState->parseIdentifier($ignoreCase);
if ($parserState->comes('(')) {
$anchor->backtrack();
if ($parserState->streql('url', $result)) {
$result = URL::parse($parserState);
} elseif ($parserState->streql('calc', $result)) {
$result = CalcFunction::parse($parserState);
} else {
$result = CSSFunction::parse($parserState, $ignoreCase);
}
}
return $result;
}
public static function parsePrimitiveValue(ParserState $parserState)
{
$parserState->consumeWhiteSpace();
if (\is_numeric($parserState->peek()) || $parserState->comes('-.') && \is_numeric($parserState->peek(1, 2)) || ($parserState->comes('-') || $parserState->comes('.')) && \is_numeric($parserState->peek(1, 1))) {
$value = Size::parse($parserState);
} elseif ($parserState->comes('#') || $parserState->comes('rgb', \true) || $parserState->comes('hsl', \true)) {
$value = Color::parse($parserState);
} elseif ($parserState->comes("'") || $parserState->comes('"')) {
$value = CSSString::parse($parserState);
} elseif ($parserState->comes('progid:') && $parserState->getSettings()->usesLenientParsing()) {
$value = self::parseMicrosoftFilter($parserState);
} elseif ($parserState->comes('[')) {
$value = LineName::parse($parserState);
} elseif ($parserState->comes('U+')) {
$value = self::parseUnicodeRangeValue($parserState);
} else {
$nextCharacter = $parserState->peek(1);
try {
$value = self::parseIdentifierOrFunction($parserState);
} catch (UnexpectedTokenException $e) {
if (\in_array($nextCharacter, ['+', '-', '*', '/'], \true)) {
$value = $parserState->consume(1);
} else {
throw $e;
}
}
}
$parserState->consumeWhiteSpace();
return $value;
}
public function getArrayRepresentation(): array
{
return ['class' => $this->getShortClassName()];
}
private static function parseMicrosoftFilter(ParserState $parserState): CSSFunction
{
$function = $parserState->consumeUntil('(', \false, \true);
$arguments = Value::parseValue($parserState, [',', '=']);
return new CSSFunction($function, $arguments, ',', $parserState->currentLine());
}
private static function parseUnicodeRangeValue(ParserState $parserState): string
{
$codepointMaxLength = 6;
$range = '';
$parserState->consume('U+');
while (\true) {
if ($parserState->comes('-')) {
$codepointMaxLength = 13;
}
$range .= $parserState->consume(1);
if (\strlen($range) >= $codepointMaxLength) {
break;
}
$matchResult = \preg_match('/[A-Fa-f0-9\?-]/', $parserState->peek());
\assert(\is_int($matchResult));
if ($matchResult !== 1) {
break;
}
}
return "U+{$range}";
}
}
