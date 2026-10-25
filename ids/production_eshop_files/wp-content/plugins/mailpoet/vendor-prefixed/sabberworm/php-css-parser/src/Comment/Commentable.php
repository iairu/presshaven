<?php
declare (strict_types=1);
namespace MailPoetVendor\Sabberworm\CSS\Comment;
if (!defined('ABSPATH')) exit;
interface Commentable
{
public function addComments(array $comments): void;
public function getComments(): array;
public function setComments(array $comments): void;
}
