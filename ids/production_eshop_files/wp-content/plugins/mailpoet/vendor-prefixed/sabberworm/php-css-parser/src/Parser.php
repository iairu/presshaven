<?php
declare (strict_types=1);
namespace MailPoetVendor\Sabberworm\CSS;
if (!defined('ABSPATH')) exit;
use MailPoetVendor\Sabberworm\CSS\CSSList\Document;
use MailPoetVendor\Sabberworm\CSS\Parsing\ParserState;
use MailPoetVendor\Sabberworm\CSS\Parsing\SourceException;
class Parser
{
private $parserState;
public function __construct(string $text, ?Settings $parserSettings = null, int $lineNumber = 1)
{
if ($parserSettings === null) {
$parserSettings = Settings::create();
}
$this->parserState = new ParserState($text, $parserSettings, $lineNumber);
}
public function parse(): Document
{
return Document::parse($this->parserState);
}
}
