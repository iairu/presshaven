<?php
declare (strict_types=1);
namespace MailPoetVendor\Doctrine\DBAL\Platforms\Keywords;
if (!defined('ABSPATH')) exit;
use MailPoetVendor\Doctrine\Deprecations\Deprecation;
use function array_merge;
class MariaDb123Keywords extends MariaDb117Keywords
{
public function getName(): string
{
Deprecation::triggerIfCalledFromOutside('doctrine/dbal', 'https://github.com/doctrine/dbal/pull/5433', 'MariaDb123Keywords::getName() is deprecated.');
return 'MariaDb123';
}
protected function getKeywords(): array
{
$keywords = parent::getKeywords();
$keywords = array_merge($keywords, ['TO_DATE']);
return $keywords;
}
}
