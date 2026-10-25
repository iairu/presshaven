<?php
declare (strict_types=1);
namespace MailPoetVendor\Sabberworm\CSS\Property;
if (!defined('ABSPATH')) exit;
use MailPoetVendor\Sabberworm\CSS\Comment\Comment;
use MailPoetVendor\Sabberworm\CSS\OutputFormat;
use MailPoetVendor\Sabberworm\CSS\Parsing\ParserState;
use MailPoetVendor\Sabberworm\CSS\Parsing\UnexpectedTokenException;
use MailPoetVendor\Sabberworm\CSS\Property\Selector\Combinator;
use MailPoetVendor\Sabberworm\CSS\Property\Selector\Component;
use MailPoetVendor\Sabberworm\CSS\Property\Selector\CompoundSelector;
use MailPoetVendor\Sabberworm\CSS\Renderable;
use MailPoetVendor\Sabberworm\CSS\Settings;
use MailPoetVendor\Sabberworm\CSS\ShortClassNameProvider;
class Selector implements Renderable
{
use ShortClassNameProvider;
public const SELECTOR_VALIDATION_RX = '/
        ^(
            # not whitespace only
            (?!\s*+$)
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
            )*+ # zero or more times
        )$
        /ux';
private $components;
public static function isValid(string $selector): bool
{
$numberOfMatches = \preg_match(static::SELECTOR_VALIDATION_RX, $selector);
if (!\is_int($numberOfMatches)) {
throw new \RuntimeException('The selector is not valid UTF-8.', 1787284398);
}
return $numberOfMatches === 1;
}
final public function __construct($selector)
{
if (\is_string($selector)) {
$this->setSelector($selector);
} else {
$this->setComponents($selector);
}
}
private static function parseComponents(ParserState $parserState, array &$comments = []): array
{
$parserState->consumeWhiteSpace($comments);
$selectorParts = [];
while (\true) {
try {
$selectorParts[] = CompoundSelector::parse($parserState, $comments);
} catch (UnexpectedTokenException $e) {
if ($selectorParts !== [] && \end($selectorParts)->getValue() === ' ') {
\array_pop($selectorParts);
break;
} else {
throw $e;
}
}
try {
$selectorParts[] = Combinator::parse($parserState, $comments);
} catch (UnexpectedTokenException $e) {
break;
}
}
return $selectorParts;
}
public static function parse(ParserState $parserState, array &$comments = []): self
{
$selectorParts = self::parseComponents($parserState, $comments);
if (!\in_array($parserState->peek(), ['{', '}', ',', ''], \true)) {
throw new UnexpectedTokenException('`,`, `{`, `}` or EOF', $parserState->peek(5), 'literal', $parserState->currentLine());
}
return new static($selectorParts);
}
public function getComponents(): array
{
return $this->components;
}
public function setComponents(array $components): self
{
$this->components = $components;
return $this;
}
public function getSelector(): string
{
return $this->render(new OutputFormat());
}
public function setSelector(string $selector): void
{
$parserState = new ParserState($selector, Settings::create());
$components = self::parseComponents($parserState);
if (!$parserState->isEnd()) {
throw new UnexpectedTokenException('EOF', $parserState->peek(5), 'literal');
}
$this->components = $components;
}
public function getSpecificity(): int
{
return \array_sum(\array_map(static function (Component $component): int {
return $component->getSpecificity();
}, $this->components));
}
public function render(OutputFormat $outputFormat): string
{
return \implode('', \array_map(static function (Component $component) use ($outputFormat): string {
return $component->render($outputFormat);
}, $this->components));
}
public function getArrayRepresentation(): array
{
return ['class' => $this->getShortClassName(), 'components' => \array_map(static function (Component $component): array {
return $component->getArrayRepresentation();
}, $this->components)];
}
}
