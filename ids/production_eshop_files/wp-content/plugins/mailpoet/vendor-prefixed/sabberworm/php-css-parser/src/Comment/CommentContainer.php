<?php
declare (strict_types=1);
namespace MailPoetVendor\Sabberworm\CSS\Comment;
if (!defined('ABSPATH')) exit;
trait CommentContainer
{
protected $comments = [];
public function addComments(array $comments): void
{
$this->comments = \array_merge($this->comments, $comments);
}
public function getComments(): array
{
return $this->comments;
}
public function setComments(array $comments): void
{
$this->comments = $comments;
}
}
