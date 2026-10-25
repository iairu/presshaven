<?php
declare (strict_types=1);
namespace MailPoetVendor\Sabberworm\CSS;
if (!defined('ABSPATH')) exit;
final class OutputFormat
{
private $stringQuotingType = '"';
private $usesRgbHashNotation = \true;
private $renderSemicolonAfterLastRule = \true;
private $spaceAfterRuleName = ' ';
private $spaceBeforeRules = '';
private $spaceAfterRules = '';
private $spaceBetweenRules = '';
private $spaceBeforeBlocks = '';
private $spaceAfterBlocks = '';
private $spaceBetweenBlocks = "\n";
private $contentBeforeAtRuleBlock = '';
private $contentAfterAtRuleBlock = '';
private $spaceBeforeSelectorSeparator = '';
private $spaceAfterSelectorSeparator = ' ';
private $spaceAroundSelectorCombinator = ' ';
private $spaceBeforeListArgumentSeparator = '';
private $spaceBeforeListArgumentSeparators = [];
private $spaceAfterListArgumentSeparator = '';
private $spaceAfterListArgumentSeparators = [];
private $spaceBeforeOpeningBrace = ' ';
private $contentBeforeDeclarationBlock = '';
private $contentAfterDeclarationBlockSelectors = '';
private $contentAfterDeclarationBlock = '';
private $indentation = "\t";
private $shouldIgnoreExceptions = \false;
private $shouldRenderComments = \false;
private $outputFormatter;
private $nextLevelFormat;
private $indentationLevel = 0;
public function getStringQuotingType(): string
{
return $this->stringQuotingType;
}
public function setStringQuotingType(string $quotingType): self
{
$this->stringQuotingType = $quotingType;
return $this;
}
public function usesRgbHashNotation(): bool
{
return $this->usesRgbHashNotation;
}
public function setRGBHashNotation(bool $usesRgbHashNotation): self
{
$this->usesRgbHashNotation = $usesRgbHashNotation;
return $this;
}
public function shouldRenderSemicolonAfterLastRule(): bool
{
return $this->renderSemicolonAfterLastRule;
}
public function setSemicolonAfterLastRule(bool $renderSemicolonAfterLastRule): self
{
$this->renderSemicolonAfterLastRule = $renderSemicolonAfterLastRule;
return $this;
}
public function getSpaceAfterRuleName(): string
{
return $this->spaceAfterRuleName;
}
public function setSpaceAfterRuleName(string $whitespace): self
{
$this->spaceAfterRuleName = $whitespace;
return $this;
}
public function getSpaceBeforeRules(): string
{
return $this->spaceBeforeRules;
}
public function setSpaceBeforeRules(string $whitespace): self
{
$this->spaceBeforeRules = $whitespace;
return $this;
}
public function getSpaceAfterRules(): string
{
return $this->spaceAfterRules;
}
public function setSpaceAfterRules(string $whitespace): self
{
$this->spaceAfterRules = $whitespace;
return $this;
}
public function getSpaceBetweenRules(): string
{
return $this->spaceBetweenRules;
}
public function setSpaceBetweenRules(string $whitespace): self
{
$this->spaceBetweenRules = $whitespace;
return $this;
}
public function getSpaceBeforeBlocks(): string
{
return $this->spaceBeforeBlocks;
}
public function setSpaceBeforeBlocks(string $whitespace): self
{
$this->spaceBeforeBlocks = $whitespace;
return $this;
}
public function getSpaceAfterBlocks(): string
{
return $this->spaceAfterBlocks;
}
public function setSpaceAfterBlocks(string $whitespace): self
{
$this->spaceAfterBlocks = $whitespace;
return $this;
}
public function getSpaceBetweenBlocks(): string
{
return $this->spaceBetweenBlocks;
}
public function setSpaceBetweenBlocks(string $whitespace): self
{
$this->spaceBetweenBlocks = $whitespace;
return $this;
}
public function getContentBeforeAtRuleBlock(): string
{
return $this->contentBeforeAtRuleBlock;
}
public function setBeforeAtRuleBlock(string $content): self
{
$this->contentBeforeAtRuleBlock = $content;
return $this;
}
public function getContentAfterAtRuleBlock(): string
{
return $this->contentAfterAtRuleBlock;
}
public function setAfterAtRuleBlock(string $content): self
{
$this->contentAfterAtRuleBlock = $content;
return $this;
}
public function getSpaceBeforeSelectorSeparator(): string
{
return $this->spaceBeforeSelectorSeparator;
}
public function setSpaceBeforeSelectorSeparator(string $whitespace): self
{
$this->spaceBeforeSelectorSeparator = $whitespace;
return $this;
}
public function getSpaceAfterSelectorSeparator(): string
{
return $this->spaceAfterSelectorSeparator;
}
public function setSpaceAfterSelectorSeparator(string $whitespace): self
{
$this->spaceAfterSelectorSeparator = $whitespace;
return $this;
}
public function getSpaceAroundSelectorCombinator(): string
{
return $this->spaceAroundSelectorCombinator;
}
public function setSpaceAroundSelectorCombinator(string $whitespace): self
{
$this->spaceAroundSelectorCombinator = $whitespace;
return $this;
}
public function getSpaceBeforeListArgumentSeparator(): string
{
return $this->spaceBeforeListArgumentSeparator;
}
public function setSpaceBeforeListArgumentSeparator(string $whitespace): self
{
$this->spaceBeforeListArgumentSeparator = $whitespace;
return $this;
}
public function getSpaceBeforeListArgumentSeparators(): array
{
return $this->spaceBeforeListArgumentSeparators;
}
public function setSpaceBeforeListArgumentSeparators(array $separatorSpaces): self
{
$this->spaceBeforeListArgumentSeparators = $separatorSpaces;
return $this;
}
public function getSpaceAfterListArgumentSeparator(): string
{
return $this->spaceAfterListArgumentSeparator;
}
public function setSpaceAfterListArgumentSeparator(string $whitespace): self
{
$this->spaceAfterListArgumentSeparator = $whitespace;
return $this;
}
public function getSpaceAfterListArgumentSeparators(): array
{
return $this->spaceAfterListArgumentSeparators;
}
public function setSpaceAfterListArgumentSeparators(array $separatorSpaces): self
{
$this->spaceAfterListArgumentSeparators = $separatorSpaces;
return $this;
}
public function getSpaceBeforeOpeningBrace(): string
{
return $this->spaceBeforeOpeningBrace;
}
public function setSpaceBeforeOpeningBrace(string $whitespace): self
{
$this->spaceBeforeOpeningBrace = $whitespace;
return $this;
}
public function getContentBeforeDeclarationBlock(): string
{
return $this->contentBeforeDeclarationBlock;
}
public function setBeforeDeclarationBlock(string $content): self
{
$this->contentBeforeDeclarationBlock = $content;
return $this;
}
public function getContentAfterDeclarationBlockSelectors(): string
{
return $this->contentAfterDeclarationBlockSelectors;
}
public function setAfterDeclarationBlockSelectors(string $content): self
{
$this->contentAfterDeclarationBlockSelectors = $content;
return $this;
}
public function getContentAfterDeclarationBlock(): string
{
return $this->contentAfterDeclarationBlock;
}
public function setAfterDeclarationBlock(string $content): self
{
$this->contentAfterDeclarationBlock = $content;
return $this;
}
public function getIndentation(): string
{
return $this->indentation;
}
public function setIndentation(string $indentation): self
{
$this->indentation = $indentation;
return $this;
}
public function shouldIgnoreExceptions(): bool
{
return $this->shouldIgnoreExceptions;
}
public function setIgnoreExceptions(bool $ignoreExceptions): self
{
$this->shouldIgnoreExceptions = $ignoreExceptions;
return $this;
}
public function shouldRenderComments(): bool
{
return $this->shouldRenderComments;
}
public function setRenderComments(bool $renderComments): self
{
$this->shouldRenderComments = $renderComments;
return $this;
}
public function getIndentationLevel(): int
{
return $this->indentationLevel;
}
public function indentWithTabs(int $numberOfTabs = 1): self
{
return $this->setIndentation(\str_repeat("\t", $numberOfTabs));
}
public function indentWithSpaces(int $numberOfSpaces = 2): self
{
return $this->setIndentation(\str_repeat(' ', $numberOfSpaces));
}
public function nextLevel(): self
{
if ($this->nextLevelFormat === null) {
$this->nextLevelFormat = clone $this;
$this->nextLevelFormat->indentationLevel++;
$this->nextLevelFormat->outputFormatter = null;
}
return $this->nextLevelFormat;
}
public function beLenient(): void
{
$this->shouldIgnoreExceptions = \true;
}
public function getFormatter(): OutputFormatter
{
if ($this->outputFormatter === null) {
$this->outputFormatter = new OutputFormatter($this);
}
return $this->outputFormatter;
}
public static function create(): self
{
return new OutputFormat();
}
public static function createCompact(): self
{
$format = self::create();
$format->setSpaceBeforeRules('')->setSpaceBetweenRules('')->setSpaceAfterRules('')->setSpaceBeforeBlocks('')->setSpaceBetweenBlocks('')->setSpaceAfterBlocks('')->setSpaceAfterRuleName('')->setSpaceBeforeOpeningBrace('')->setSpaceAfterSelectorSeparator('')->setSpaceAroundSelectorCombinator('')->setSemicolonAfterLastRule(\false)->setRenderComments(\false);
return $format;
}
public static function createPretty(): self
{
$format = self::create();
$format->setSpaceBeforeRules("\n")->setSpaceBetweenRules("\n")->setSpaceAfterRules("\n")->setSpaceBeforeBlocks("\n")->setSpaceBetweenBlocks("\n\n")->setSpaceAfterBlocks("\n")->setSpaceAfterListArgumentSeparators([',' => ' '])->setRenderComments(\true);
return $format;
}
}
