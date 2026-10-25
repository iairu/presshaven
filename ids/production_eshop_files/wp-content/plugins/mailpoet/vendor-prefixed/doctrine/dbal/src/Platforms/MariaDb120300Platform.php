<?php
declare (strict_types=1);
namespace MailPoetVendor\Doctrine\DBAL\Platforms;
if (!defined('ABSPATH')) exit;
use MailPoetVendor\Doctrine\Deprecations\Deprecation;
class MariaDb120300Platform extends MariaDb110700Platform
{
protected function getReservedKeywordsClass(): string
{
Deprecation::triggerIfCalledFromOutside('doctrine/dbal', 'https://github.com/doctrine/dbal/issues/4510', 'MariaDb120300Platform::getReservedKeywordsClass() is deprecated,' . ' use MariaDb120300Platform::createReservedKeywordsList() instead.');
return Keywords\MariaDb123Keywords::class;
}
}
