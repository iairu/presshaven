<?php
declare (strict_types=1);
namespace MailPoetVendor\Pelago\Emogrifier\HtmlProcessor;
if (!defined('ABSPATH')) exit;
use MailPoetVendor\Pelago\Emogrifier\Utilities\Preg;
abstract class AbstractHtmlProcessor
{
protected const DEFAULT_DOCUMENT_TYPE = '<!DOCTYPE html>';
protected const CONTENT_TYPE_META_TAG = '<meta http-equiv="Content-Type" content="text/html; charset=utf-8">';
protected const PHP_UNRECOGNIZED_VOID_TAGNAME_MATCHER = '(?:command|embed|keygen|source|track|wbr)';
protected const TAGNAME_ALLOWED_BEFORE_BODY_MATCHER = '(?:html|head|base|command|link|meta|noscript|script|style|template|title)';
protected const HTML_COMMENT_PATTERN = '/<!--[^-]*+(?:-(?!->)[^-]*+)*+(?:-->|$)/';
protected const HTML_TEMPLATE_ELEMENT_PATTERN = '%<template[\s>][^<]*+(?:<(?!/template>)[^<]*+)*+(?:</template>|$)%i';
private $domDocument;
protected $xPath;
final private function __construct()
{
}
public static function fromHtml(string $unprocessedHtml): self
{
if ($unprocessedHtml === '') {
throw new \InvalidArgumentException('The provided HTML must not be empty.', 1515763647);
}
$instance = new static();
$instance->setHtml($unprocessedHtml);
\assert($instance->domDocument instanceof \DOMDocument);
\assert($instance->xPath instanceof \DOMXPath);
return $instance;
}
public static function fromDomDocument(\DOMDocument $document): self
{
$instance = new static();
$instance->setDomDocument($document);
\assert($instance->domDocument instanceof \DOMDocument);
\assert($instance->xPath instanceof \DOMXPath);
return $instance;
}
private function setHtml(string $html): void
{
$this->createUnifiedDomDocument($html);
}
public function getDomDocument(): \DOMDocument
{
\assert($this->domDocument instanceof \DOMDocument);
return $this->domDocument;
}
private function setDomDocument(\DOMDocument $domDocument): void
{
$this->domDocument = $domDocument;
$this->xPath = new \DOMXPath($domDocument);
}
public function render(): string
{
return $this->getHtml();
}
public function renderBodyContent(): string
{
$bodyNodeHtml = $this->getHtml($this->getBodyElement());
return (new Preg())->replace('%</?+body(?:\s[^>]*+)?+>%', '', $bodyNodeHtml);
}
private function getHtml(?\DOMNode $node = null): string
{
$html = $this->getDomDocument()->saveHTML($node);
if (!\is_string($html)) {
throw new \RuntimeException('`DOMDocument::saveHTML()` failed.', 1773018082);
}
return $this->removeSelfClosingTagsClosingTags($html);
}
private function removeSelfClosingTagsClosingTags(string $html): string
{
return (new Preg())->replace('%</' . self::PHP_UNRECOGNIZED_VOID_TAGNAME_MATCHER . '>%', '', $html);
}
protected function getHtmlElement(): \DOMElement
{
$htmlElement = $this->getDomDocument()->getElementsByTagName('html')->item(0);
if (!$htmlElement instanceof \DOMElement) {
throw new \UnexpectedValueException('There is no HTML element although there should be one.', 1569930853);
}
return $htmlElement;
}
private function getBodyElement(): \DOMElement
{
$node = $this->getDomDocument()->getElementsByTagName('body')->item(0);
if (!$node instanceof \DOMElement) {
throw new \RuntimeException('There is no body element.', 1617922607);
}
return $node;
}
private function createUnifiedDomDocument(string $html): void
{
$this->createRawDomDocument($html);
$this->ensureExistenceOfBodyElement();
}
private function createRawDomDocument(string $html): void
{
$domDocument = new \DOMDocument();
$domDocument->strictErrorChecking = \false;
$domDocument->formatOutput = \false;
$libXmlState = \libxml_use_internal_errors(\true);
$domDocument->loadHTML($this->prepareHtmlForDomConversion($html), \LIBXML_PARSEHUGE);
\libxml_clear_errors();
\libxml_use_internal_errors($libXmlState);
$this->setDomDocument($domDocument);
}
private function prepareHtmlForDomConversion(string $html): string
{
$htmlWithSelfClosingSlashes = $this->ensurePhpUnrecognizedSelfClosingTagsAreXml($html);
$htmlWithDocumentType = $this->ensureDocumentType($htmlWithSelfClosingSlashes);
return $this->addContentTypeMetaTag($htmlWithDocumentType);
}
private function ensureDocumentType(string $html): string
{
$hasDocumentType = \stripos($html, '<!DOCTYPE') !== \false;
if ($hasDocumentType) {
return $this->normalizeDocumentType($html);
}
return self::DEFAULT_DOCUMENT_TYPE . $html;
}
private function normalizeDocumentType(string $html): string
{
$result = (new Preg())->replace('/<!DOCTYPE\s++html(?=[\s>])/i', '<!DOCTYPE html', $html, 1);
\assert($result !== '');
return $result;
}
private function addContentTypeMetaTag(string $html): string
{
if ($this->hasContentTypeMetaTagInHead($html)) {
return $html;
}
$preg = new Preg();
$hasHeadTag = $preg->match('/<head[\s>]/i', $html) !== 0;
$hasHtmlTag = \stripos($html, '<html') !== \false;
if ($hasHeadTag) {
$reworkedHtml = $preg->replace('/<head(?=[\s>])([^>]*+)>/i', '<head$1>' . self::CONTENT_TYPE_META_TAG, $html);
} elseif ($hasHtmlTag) {
$reworkedHtml = $preg->replace('/<html(.*?)>/is', '<html$1><head>' . self::CONTENT_TYPE_META_TAG . '</head>', $html);
} else {
$reworkedHtml = self::CONTENT_TYPE_META_TAG . $html;
}
\assert($reworkedHtml !== '');
return $reworkedHtml;
}
private function hasContentTypeMetaTagInHead(string $html): bool
{
(new Preg())->match('%
                (?(DEFINE)
                    # the target `http-equiv` attribute match
                    (?<target_attribute>
                        http-equiv=(["\']?+)Content-Type\g{-1}
                        # must be followed by one of these characters
                        [\s/>]
                    )
                    # the target `meta` element match without the opening `<`
                    (?<target>
                        meta(?=\s)
                        # one or other of these
                        (?:
                            # one or more characters other than `>` or space
                            [^>\s]++
                            |
                            # space not followed by the target `http-equiv` attribute
                            \s(?!(?&target_attribute))
                        )
                        # any number of times (including zero)
                        *+
                        \s(?&target_attribute)
                    )
                )
                # start of `subject`
                ^
                # one or other of these
                (?:
                    # one or more characters other than `<`
                    [^<]++
                    |
                    # `<` not followed by `target`
                    <(?!(?&target))
                )
                # any number of times (including zero)
                *+
                # followed by the target, not captured
                (?=<(?&target))
            %isx', $html, $matches);
if (isset($matches[0])) {
$htmlBefore = $matches[0];
try {
$hasContentTypeMetaTagInHead = !$this->hasEndOfHeadElement($htmlBefore);
} catch (\RuntimeException $exception) {
\trigger_error($exception->getMessage());
$hasContentTypeMetaTagInHead = \true;
}
} else {
$hasContentTypeMetaTagInHead = \false;
}
return $hasContentTypeMetaTagInHead;
}
private function hasEndOfHeadElement(string $html): bool
{
if ((new Preg())->match('%<(?!' . self::TAGNAME_ALLOWED_BEFORE_BODY_MATCHER . '[\s/>])\w|</head>%i', $html) !== 0) {
$htmlWithoutCommentsOrTemplates = $this->removeHtmlTemplateElements($this->removeHtmlComments($html));
$hasEndOfHeadElement = $htmlWithoutCommentsOrTemplates === $html || $this->hasEndOfHeadElement($htmlWithoutCommentsOrTemplates);
} else {
$hasEndOfHeadElement = \false;
}
return $hasEndOfHeadElement;
}
private function removeHtmlComments(string $html): string
{
return (new Preg())->replace(self::HTML_COMMENT_PATTERN, '', $html);
}
private function removeHtmlTemplateElements(string $html): string
{
return (new Preg())->replace(self::HTML_TEMPLATE_ELEMENT_PATTERN, '', $html);
}
private function ensurePhpUnrecognizedSelfClosingTagsAreXml(string $html): string
{
return (new Preg())->replace('%<' . self::PHP_UNRECOGNIZED_VOID_TAGNAME_MATCHER . '\b[^>]*+(?<!/)(?=>)%', '$0/', $html);
}
private function ensureExistenceOfBodyElement(): void
{
if ($this->getDomDocument()->getElementsByTagName('body')->item(0) instanceof \DOMElement) {
return;
}
$this->getHtmlElement()->appendChild($this->getDomDocument()->createElement('body'));
}
}
