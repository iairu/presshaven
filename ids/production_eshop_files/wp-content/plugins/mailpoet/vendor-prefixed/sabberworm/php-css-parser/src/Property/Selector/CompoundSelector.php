<?php
declare (strict_types=1);
namespace MailPoetVendor\Sabberworm\CSS\Property\Selector;
if (!defined('ABSPATH')) exit;
use MailPoetVendor\Sabberworm\CSS\Comment\Comment;
use MailPoetVendor\Sabberworm\CSS\OutputFormat;
use MailPoetVendor\Sabberworm\CSS\Parsing\ParserState;
use MailPoetVendor\Sabberworm\CSS\Parsing\UnexpectedTokenException;
use MailPoetVendor\Sabberworm\CSS\ShortClassNameProvider;
class CompoundSelector implements Component
{
use ShortClassNameProvider;
private const PARSER_STOP_CHARACTERS = ['{', '}', '\'', '"', '(', ')', '[', ']', ',', ' ', "\t", "\n", "\r", '>', '+', '~', ParserState::EOF, ''];
private const SELECTOR_VALIDATION_RX = '/
        ^
            # not starting with whitespace
            (?!\s)
            (?:
                (?:
                    # any sequence of valid unescaped characters, except quotes
                    [a-zA-Z0-9\x{00A0}-\x{FFFF}_^$|*=~\[\]()\-\s\.:#+>,]++
                    |
                    # one or more escaped characters
                    (?:\\\\.)++
                    |
                    # quoted text, like in `[id="example"]`
                    (?:
                        # opening quote
                        ([\'"])
                        (?:
                            # sequence of characters except closing quote or backslash
                            (?:(?!\g{-1}|\\\\).)++
                            |
                            # one or more escaped characters
                            (?:\\\\.)++
                        )*+ # zero or more times
                        # closing quote or end (unmatched quote is currently allowed)
                        (?:\g{-1}|$)
                    )
                )++ # one or more times
                |
                # keyframe animation progress percentage (e.g. 50%)
                (?:\d++%)
            )
            # not ending with whitespace
            (?<!\s)
        $
        /ux';
private $value;
public function __construct(string $value)
{
$this->setValue($value);
}
public static function parse(ParserState $parserState, array &$comments = []): self
{
$selectorParts = [];
$stringWrapperCharacter = null;
$functionNestingLevel = 0;
$isWithinAttribute = \false;
while (\true) {
$selectorParts[] = $parserState->consumeUntil(self::PARSER_STOP_CHARACTERS, \false, \false, $comments);
$nextCharacter = $parserState->peek();
switch ($nextCharacter) {
case '':
break 2;
case '\'':
case '"':
$lastPart = \end($selectorParts);
$backslashCount = \strspn(\strrev($lastPart), '\\');
$quoteIsEscaped = $backslashCount % 2 === 1;
if (!$quoteIsEscaped) {
if (!\is_string($stringWrapperCharacter)) {
$stringWrapperCharacter = $nextCharacter;
} elseif ($stringWrapperCharacter === $nextCharacter) {
$stringWrapperCharacter = null;
}
}
break;
case '(':
if (!\is_string($stringWrapperCharacter)) {
++$functionNestingLevel;
}
break;
case ')':
if (!\is_string($stringWrapperCharacter)) {
if ($functionNestingLevel <= 0) {
throw new UnexpectedTokenException('anything but', ')', 'literal', $parserState->currentLine());
}
--$functionNestingLevel;
}
break;
case '[':
if (!\is_string($stringWrapperCharacter)) {
if ($isWithinAttribute) {
throw new UnexpectedTokenException('anything but', '[', 'literal', $parserState->currentLine());
}
$isWithinAttribute = \true;
}
break;
case ']':
if (!\is_string($stringWrapperCharacter)) {
if (!$isWithinAttribute) {
throw new UnexpectedTokenException('anything but', ']', 'literal', $parserState->currentLine());
}
$isWithinAttribute = \false;
}
break;
case '{':
case '}':
if (!\is_string($stringWrapperCharacter)) {
break 2;
}
break;
case ',':
case ' ':
case "\t":
case "\n":
case "\r":
case '>':
case '+':
case '~':
if (!\is_string($stringWrapperCharacter) && $functionNestingLevel === 0 && !$isWithinAttribute) {
break 2;
}
break;
}
$selectorParts[] = $parserState->consume(1);
}
if ($functionNestingLevel !== 0) {
throw new UnexpectedTokenException(')', $nextCharacter, 'literal', $parserState->currentLine());
}
if (\is_string($stringWrapperCharacter)) {
throw new UnexpectedTokenException($stringWrapperCharacter, $nextCharacter, 'literal', $parserState->currentLine());
}
$value = \implode('', $selectorParts);
if ($value === '') {
throw new UnexpectedTokenException('selector', $nextCharacter, 'literal', $parserState->currentLine());
}
if (!self::isValid($value)) {
throw new UnexpectedTokenException('Selector component is not valid:', '`' . $value . '`', 'custom', $parserState->currentLine());
}
return new self($value);
}
public function getValue(): string
{
return $this->value;
}
public function setValue(string $value): void
{
if (!self::isValid($value)) {
throw new \UnexpectedValueException('`' . $value . '` is not a valid compound selector.');
}
$this->value = $value;
}
public function getSpecificity(): int
{
return SpecificityCalculator::calculate($this->value);
}
public function render(OutputFormat $outputFormat): string
{
return $this->getValue();
}
public function getArrayRepresentation(): array
{
return ['class' => $this->getShortClassName(), 'value' => $this->value];
}
private static function isValid(string $value): bool
{
$numberOfMatches = \preg_match(self::SELECTOR_VALIDATION_RX, $value);
if (!\is_int($numberOfMatches)) {
throw new \RuntimeException('The selector is not valid UTF-8.', 1787283476);
}
return $numberOfMatches === 1;
}
}
