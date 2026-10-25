<?php
declare (strict_types=1);
namespace MailPoetVendor\Doctrine\ORM\Internal;
if (!defined('ABSPATH')) exit;
use MailPoetVendor\Doctrine\ORM\Internal\TopologicalSort\CycleDetectedException;
use function array_keys;
use function spl_object_id;
final class TopologicalSort
{
private const NOT_VISITED = 1;
private const IN_PROGRESS = 2;
private const VISITED = 3;
private $nodes = [];
private $states = [];
private $edges = [];
private $sortResult = [];
public function addNode($node): void
{
$id = spl_object_id($node);
$this->nodes[$id] = $node;
$this->states[$id] = self::NOT_VISITED;
$this->edges[$id] = [];
}
public function hasNode($node): bool
{
return isset($this->nodes[spl_object_id($node)]);
}
public function addEdge($from, $to, bool $optional): void
{
$fromId = spl_object_id($from);
$toId = spl_object_id($to);
if (isset($this->edges[$fromId][$toId]) && $this->edges[$fromId][$toId] === \false) {
return;
}
$this->edges[$fromId][$toId] = $optional;
}
public function sort(): array
{
foreach (array_keys($this->nodes) as $oid) {
if ($this->states[$oid] === self::NOT_VISITED) {
$this->visit($oid);
}
}
return $this->sortResult;
}
private function visit(int $oid): void
{
if ($this->states[$oid] === self::IN_PROGRESS) {
throw new CycleDetectedException($this->nodes[$oid]);
}
if ($this->states[$oid] === self::VISITED) {
return;
}
$this->states[$oid] = self::IN_PROGRESS;
foreach ($this->edges[$oid] as $adjacentId => $optional) {
try {
$this->visit($adjacentId);
} catch (CycleDetectedException $exception) {
if ($exception->isCycleCollected()) {
throw $exception;
}
if ($optional) {
continue;
}
$this->states[$oid] = self::NOT_VISITED;
$exception->addToCycle($this->nodes[$oid]);
throw $exception;
}
}
$this->states[$oid] = self::VISITED;
$this->sortResult[] = $this->nodes[$oid];
}
}
