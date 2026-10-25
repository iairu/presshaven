<?php
declare (strict_types=1);
namespace MailPoetVendor\Sabberworm\CSS\Value;
if (!defined('ABSPATH')) exit;
use MailPoetVendor\Sabberworm\CSS\OutputFormat;
use MailPoetVendor\Sabberworm\CSS\Parsing\ParserState;
use MailPoetVendor\Sabberworm\CSS\Parsing\UnexpectedEOFException;
use MailPoetVendor\Sabberworm\CSS\Parsing\UnexpectedTokenException;
class LineName extends ValueList
{
public function __construct(array $components = [], ?int $lineNumber = null)
{
parent::__construct($components, ' ', $lineNumber);
}
public static function parse(ParserState $parserState): LineName
{
$parserState->consume('[');
$parserState->consumeWhiteSpace();
$names = [];
do {
if ($parserState->getSettings()->usesLenientParsing()) {
try {
$names[] = $parserState->parseIdentifier();
} catch (UnexpectedTokenException $e) {
if (!$parserState->comes(']')) {
throw $e;
}
}
} else {
$names[] = $parserState->parseIdentifier();
}
$parserState->consumeWhiteSpace();
} while (!$parserState->comes(']'));
$parserState->consume(']');
return new LineName($names, $parserState->currentLine());
}
public function render(OutputFormat $outputFormat): string
{
return '[' . parent::render(OutputFormat::createCompact()) . ']';
}
}
