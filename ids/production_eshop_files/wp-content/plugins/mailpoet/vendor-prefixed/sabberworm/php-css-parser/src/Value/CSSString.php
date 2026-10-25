<?php
declare (strict_types=1);
namespace MailPoetVendor\Sabberworm\CSS\Value;
if (!defined('ABSPATH')) exit;
use MailPoetVendor\Sabberworm\CSS\OutputFormat;
use MailPoetVendor\Sabberworm\CSS\Parsing\ParserState;
use MailPoetVendor\Sabberworm\CSS\Parsing\SourceException;
use MailPoetVendor\Sabberworm\CSS\Parsing\UnexpectedEOFException;
use MailPoetVendor\Sabberworm\CSS\Parsing\UnexpectedTokenException;
use MailPoetVendor\Sabberworm\CSS\ShortClassNameProvider;
class CSSString extends PrimitiveValue
{
use ShortClassNameProvider;
private $string;
public function __construct(string $string, ?int $lineNumber = null)
{
$this->string = $string;
parent::__construct($lineNumber);
}
public static function parse(ParserState $parserState): CSSString
{
$begin = $parserState->peek();
$quote = null;
if ($begin === "'") {
$quote = "'";
} elseif ($begin === '"') {
$quote = '"';
}
if ($quote !== null) {
$parserState->consume($quote);
}
$result = '';
if ($quote === null) {
while (\true) {
$matchResult = \preg_match('/[\s{}()<>\[\]]/isu', $parserState->peek());
if (!\is_int($matchResult)) {
throw new \RuntimeException('The CSS is not valid UTF-8.', 1787548272);
}
if ($matchResult !== 0) {
break;
}
$result .= $parserState->parseCharacter(\false);
}
} else {
while (!$parserState->comes($quote)) {
$content = $parserState->parseCharacter(\false);
if ($content === null) {
throw new SourceException("Non-well-formed quoted string {$parserState->peek(3)}", $parserState->currentLine());
}
$result .= $content;
}
$parserState->consume($quote);
}
return new CSSString($result, $parserState->currentLine());
}
public function setString(string $string): void
{
$this->string = $string;
}
public function getString(): string
{
return $this->string;
}
public function render(OutputFormat $outputFormat): string
{
return $outputFormat->getStringQuotingType() . $this->escape($this->string, $outputFormat) . $outputFormat->getStringQuotingType();
}
public function getArrayRepresentation(): array
{
return [
'class' => $this->getShortClassName(),
'contents' => $this->string,
];
}
private function escape(string $string, OutputFormat $outputFormat): string
{
$charactersToEscape = '\\';
$charactersToEscape .= $outputFormat->getStringQuotingType() === '"' ? '"' : "'";
$withEscapedQuotes = \addcslashes($string, $charactersToEscape);
$withNewlineEncoded = \str_replace("\n", '\A', $withEscapedQuotes);
return $withNewlineEncoded;
}
}
