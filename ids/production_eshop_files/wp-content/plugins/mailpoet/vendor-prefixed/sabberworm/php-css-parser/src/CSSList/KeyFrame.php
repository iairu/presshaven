<?php
declare (strict_types=1);
namespace MailPoetVendor\Sabberworm\CSS\CSSList;
if (!defined('ABSPATH')) exit;
use MailPoetVendor\Sabberworm\CSS\OutputFormat;
use MailPoetVendor\Sabberworm\CSS\Property\AtRule;
class KeyFrame extends CSSList implements AtRule
{
private $vendorKeyFrame = 'keyframes';
private $animationName = 'none';
public function setVendorKeyFrame(string $vendorKeyFrame): void
{
$this->vendorKeyFrame = $vendorKeyFrame;
}
public function getVendorKeyFrame(): string
{
return $this->vendorKeyFrame;
}
public function setAnimationName(string $animationName): void
{
$this->animationName = $animationName;
}
public function getAnimationName(): string
{
return $this->animationName;
}
public function render(OutputFormat $outputFormat): string
{
$formatter = $outputFormat->getFormatter();
$result = $formatter->comments($this);
$result .= "@{$this->vendorKeyFrame} {$this->animationName}{$formatter->spaceBeforeOpeningBrace()}{";
$result .= $this->renderListContents($outputFormat);
$result .= '}';
return $result;
}
public function isRootList(): bool
{
return \false;
}
public function atRuleName(): string
{
return $this->vendorKeyFrame;
}
public function atRuleArgs(): string
{
return $this->animationName;
}
}
