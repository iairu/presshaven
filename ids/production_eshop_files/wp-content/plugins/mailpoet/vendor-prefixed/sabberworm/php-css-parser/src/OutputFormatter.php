<?php
declare (strict_types=1);
namespace MailPoetVendor\Sabberworm\CSS;
if (!defined('ABSPATH')) exit;
use MailPoetVendor\Sabberworm\CSS\Comment\Commentable;
use MailPoetVendor\Sabberworm\CSS\Parsing\OutputException;
class OutputFormatter
{
private $outputFormat;
public function __construct(OutputFormat $outputFormat)
{
$this->outputFormat = $outputFormat;
}
public function space(string $name): string
{
switch ($name) {
case 'AfterRuleName':
$spaceString = $this->outputFormat->getSpaceAfterRuleName();
break;
case 'BeforeRules':
$spaceString = $this->outputFormat->getSpaceBeforeRules();
break;
case 'AfterRules':
$spaceString = $this->outputFormat->getSpaceAfterRules();
break;
case 'BetweenRules':
$spaceString = $this->outputFormat->getSpaceBetweenRules();
break;
case 'BeforeBlocks':
$spaceString = $this->outputFormat->getSpaceBeforeBlocks();
break;
case 'AfterBlocks':
$spaceString = $this->outputFormat->getSpaceAfterBlocks();
break;
case 'BetweenBlocks':
$spaceString = $this->outputFormat->getSpaceBetweenBlocks();
break;
case 'BeforeSelectorSeparator':
$spaceString = $this->outputFormat->getSpaceBeforeSelectorSeparator();
break;
case 'AfterSelectorSeparator':
$spaceString = $this->outputFormat->getSpaceAfterSelectorSeparator();
break;
case 'BeforeOpeningBrace':
$spaceString = $this->outputFormat->getSpaceBeforeOpeningBrace();
break;
case 'BeforeListArgumentSeparator':
$spaceString = $this->outputFormat->getSpaceBeforeListArgumentSeparator();
break;
case 'AfterListArgumentSeparator':
$spaceString = $this->outputFormat->getSpaceAfterListArgumentSeparator();
break;
default:
throw new \InvalidArgumentException("Unknown space type: {$name}", 1740049248);
}
return $this->prepareSpace($spaceString);
}
public function spaceAfterRuleName(): string
{
return $this->space('AfterRuleName');
}
public function spaceBeforeRules(): string
{
return $this->space('BeforeRules');
}
public function spaceAfterRules(): string
{
return $this->space('AfterRules');
}
public function spaceBetweenRules(): string
{
return $this->space('BetweenRules');
}
public function spaceBeforeBlocks(): string
{
return $this->space('BeforeBlocks');
}
public function spaceAfterBlocks(): string
{
return $this->space('AfterBlocks');
}
public function spaceBetweenBlocks(): string
{
return $this->space('BetweenBlocks');
}
public function spaceBeforeSelectorSeparator(): string
{
return $this->space('BeforeSelectorSeparator');
}
public function spaceAfterSelectorSeparator(): string
{
return $this->space('AfterSelectorSeparator');
}
public function spaceBeforeListArgumentSeparator(string $separator): string
{
$spaceForSeparator = $this->outputFormat->getSpaceBeforeListArgumentSeparators();
return $spaceForSeparator[$separator] ?? $this->space('BeforeListArgumentSeparator');
}
public function spaceAfterListArgumentSeparator(string $separator): string
{
$spaceForSeparator = $this->outputFormat->getSpaceAfterListArgumentSeparators();
return $spaceForSeparator[$separator] ?? $this->space('AfterListArgumentSeparator');
}
public function spaceBeforeOpeningBrace(): string
{
return $this->space('BeforeOpeningBrace');
}
public function safely(callable $callable): ?string
{
if ($this->outputFormat->shouldIgnoreExceptions()) {
try {
return $callable();
} catch (OutputException $e) {
return null;
}
} else {
return $callable();
}
}
public function implode(string $separator, array $values, bool $increaseLevel = \false): string
{
$result = '';
$outputFormat = $this->outputFormat;
if ($increaseLevel) {
$outputFormat = $outputFormat->nextLevel();
}
$isFirst = \true;
foreach ($values as $value) {
if ($isFirst) {
$isFirst = \false;
} else {
$result .= $separator;
}
if ($value instanceof Renderable) {
$result .= $value->render($outputFormat);
} else {
$result .= $value;
}
}
return $result;
}
public function removeLastSemicolon(string $string): string
{
if ($this->outputFormat->shouldRenderSemicolonAfterLastRule()) {
return $string;
}
$parts = \explode(';', $string);
if (\count($parts) < 2) {
return $parts[0];
}
$lastPart = \array_pop($parts);
$nextToLastPart = \array_pop($parts);
\array_push($parts, $nextToLastPart . $lastPart);
return \implode(';', $parts);
}
public function comments(Commentable $commentable): string
{
if (!$this->outputFormat->shouldRenderComments()) {
return '';
}
$result = '';
$comments = $commentable->getComments();
$lastCommentIndex = \count($comments) - 1;
foreach ($comments as $i => $comment) {
$result .= $comment->render($this->outputFormat);
$result .= $i === $lastCommentIndex ? $this->spaceAfterBlocks() : $this->spaceBetweenBlocks();
}
return $result;
}
private function prepareSpace(string $spaceString): string
{
return \str_replace("\n", "\n" . $this->indent(), $spaceString);
}
private function indent(): string
{
return \str_repeat($this->outputFormat->getIndentation(), $this->outputFormat->getIndentationLevel());
}
}
