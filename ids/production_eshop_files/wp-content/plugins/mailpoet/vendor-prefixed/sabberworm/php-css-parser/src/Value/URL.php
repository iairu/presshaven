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
class URL extends PrimitiveValue
{
use ShortClassNameProvider;
private $url;
public function __construct(CSSString $url, ?int $lineNumber = null)
{
parent::__construct($lineNumber);
$this->url = $url;
}
public static function parse(ParserState $parserState): URL
{
$anchor = $parserState->anchor();
$identifier = '';
for ($i = 0; $i < 3; $i++) {
$character = $parserState->parseCharacter(\true);
if ($character === null) {
break;
}
$identifier .= $character;
}
$useUrl = $parserState->streql($identifier, 'url');
if ($useUrl) {
$parserState->consumeWhiteSpace();
$parserState->consume('(');
} else {
$anchor->backtrack();
}
$parserState->consumeWhiteSpace();
$result = new URL(CSSString::parse($parserState), $parserState->currentLine());
if ($useUrl) {
$parserState->consumeWhiteSpace();
$parserState->consume(')');
}
return $result;
}
public function setURL(CSSString $url): void
{
$this->url = $url;
}
public function getURL(): CSSString
{
return $this->url;
}
public function render(OutputFormat $outputFormat): string
{
return "url({$this->url->render($outputFormat)})";
}
public function getArrayRepresentation(): array
{
return [
'class' => $this->getShortClassName(),
'uri' => $this->url->getArrayRepresentation(),
];
}
}
