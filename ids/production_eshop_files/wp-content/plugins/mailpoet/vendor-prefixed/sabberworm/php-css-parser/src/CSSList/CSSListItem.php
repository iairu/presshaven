<?php
declare (strict_types=1);
namespace MailPoetVendor\Sabberworm\CSS\CSSList;
if (!defined('ABSPATH')) exit;
use MailPoetVendor\Sabberworm\CSS\Comment\Commentable;
use MailPoetVendor\Sabberworm\CSS\Renderable;
interface CSSListItem extends Commentable, Renderable
{
}
