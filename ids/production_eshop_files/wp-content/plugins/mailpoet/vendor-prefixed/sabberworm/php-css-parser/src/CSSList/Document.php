<?php
declare (strict_types=1);
namespace MailPoetVendor\Sabberworm\CSS\CSSList;
if (!defined('ABSPATH')) exit;
use MailPoetVendor\Sabberworm\CSS\OutputFormat;
use MailPoetVendor\Sabberworm\CSS\Parsing\ParserState;
use MailPoetVendor\Sabberworm\CSS\Parsing\SourceException;
use MailPoetVendor\Sabberworm\CSS\Property\Selector;
class Document extends CSSBlockList
{
public static function parse(ParserState $parserState): Document
{
$document = new Document($parserState->currentLine());
CSSList::parseList($parserState, $document);
return $document;
}
public function getSelectorsBySpecificity(?string $specificitySearch = null): array
{
return $this->getAllSelectors($specificitySearch);
}
public function render(?OutputFormat $outputFormat = null): string
{
if ($outputFormat === null) {
$outputFormat = new OutputFormat();
}
return $outputFormat->getFormatter()->comments($this) . $this->renderListContents($outputFormat);
}
public function isRootList(): bool
{
return \true;
}
}
