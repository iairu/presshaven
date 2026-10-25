<?php
declare (strict_types=1);
namespace MailPoetVendor\Sabberworm\CSS\Position;
if (!defined('ABSPATH')) exit;
trait Position
{
protected $lineNumber;
protected $columnNumber;
public function getLineNumber(): ?int
{
return $this->lineNumber;
}
public function getColumnNumber(): ?int
{
return $this->columnNumber;
}
public function setPosition(?int $lineNumber, ?int $columnNumber = null): Positionable
{
$this->lineNumber = $lineNumber;
$this->columnNumber = $columnNumber;
return $this;
}
}
