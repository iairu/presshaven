<?php
namespace MailPoetVendor\Twig\Cache;
if (!defined('ABSPATH')) exit;
class ReadOnlyFilesystemCache extends FilesystemCache
{
public function write(string $key, string $content): void
{
}
}
