<?php
declare (strict_types=1);
namespace MailPoetVendor\Sabberworm\CSS\Comment;
if (!defined('ABSPATH')) exit;
use MailPoetVendor\Sabberworm\CSS\OutputFormat;
use MailPoetVendor\Sabberworm\CSS\Position\Position;
use MailPoetVendor\Sabberworm\CSS\Position\Positionable;
use MailPoetVendor\Sabberworm\CSS\Renderable;
use MailPoetVendor\Sabberworm\CSS\ShortClassNameProvider;
class Comment implements Positionable, Renderable
{
use Position;
use ShortClassNameProvider;
protected $commentText;
public function __construct(string $commentText = '', ?int $lineNumber = null)
{
$this->commentText = $commentText;
$this->setPosition($lineNumber);
}
public function getComment(): string
{
return $this->commentText;
}
public function setComment(string $commentText): void
{
$this->commentText = $commentText;
}
public function render(OutputFormat $outputFormat): string
{
return '/*' . $this->commentText . '*/';
}
public function getArrayRepresentation(): array
{
return [
'class' => $this->getShortClassName(),
'contents' => $this->commentText,
];
}
}
