<?php
namespace Automattic\WooCommerce\EmailEditorVendor\Sabberworm\CSS;
if (!defined('ABSPATH')) exit;
use Automattic\WooCommerce\EmailEditorVendor\Sabberworm\CSS\CSSList\Document;
use Automattic\WooCommerce\EmailEditorVendor\Sabberworm\CSS\Parsing\ParserState;
use Automattic\WooCommerce\EmailEditorVendor\Sabberworm\CSS\Parsing\SourceException;
class Parser
{
private $oParserState;
public function __construct($sText, $oParserSettings = null, $iLineNo = 1)
{
if ($oParserSettings === null) {
$oParserSettings = Settings::create();
}
$this->oParserState = new ParserState($sText, $oParserSettings, $iLineNo);
}
public function setCharset($sCharset)
{
$this->oParserState->setCharset($sCharset);
}
public function getCharset()
{
$this->oParserState->getCharset();
}
public function parse()
{
return Document::parse($this->oParserState);
}
}
