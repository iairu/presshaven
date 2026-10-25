<?php
declare (strict_types=1);
namespace MailPoetVendor\Sabberworm\CSS;
if (!defined('ABSPATH')) exit;
class Settings
{
private $multibyteSupport;
private $defaultCharset = 'utf-8';
private $lenientParsing = \true;
private function __construct()
{
$this->multibyteSupport = \extension_loaded('mbstring');
}
public static function create(): self
{
return new Settings();
}
public function withMultibyteSupport(bool $multibyteSupport = \true): self
{
$this->multibyteSupport = $multibyteSupport;
return $this;
}
public function withDefaultCharset(string $defaultCharset): self
{
$this->defaultCharset = $defaultCharset;
return $this;
}
public function withLenientParsing(bool $usesLenientParsing = \true): self
{
$this->lenientParsing = $usesLenientParsing;
return $this;
}
public function beStrict(): self
{
return $this->withLenientParsing(\false);
}
public function hasMultibyteSupport(): bool
{
return $this->multibyteSupport;
}
public function getDefaultCharset(): string
{
return $this->defaultCharset;
}
public function usesLenientParsing(): bool
{
return $this->lenientParsing;
}
}
