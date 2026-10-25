<?php
declare (strict_types=1);
namespace MailPoetVendor\Doctrine\ORM\Id;
if (!defined('ABSPATH')) exit;
use MailPoetVendor\Doctrine\ORM\EntityManagerInterface;
class TableGenerator extends AbstractIdGenerator
{
private $tableName;
private $sequenceName;
private $allocationSize;
private $nextValue;
private $maxValue;
public function __construct($tableName, $sequenceName = 'default', $allocationSize = 10)
{
$this->tableName = $tableName;
$this->sequenceName = $sequenceName;
$this->allocationSize = $allocationSize;
}
public function generateId(EntityManagerInterface $em, $entity)
{
if ($this->maxValue === null || $this->nextValue === $this->maxValue) {
$conn = $em->getConnection();
if ($conn->getTransactionNestingLevel() === 0) {
$sql = $conn->getDatabasePlatform()->getTableHiLoCurrentValSql($this->tableName, $this->sequenceName);
$currentLevel = $conn->fetchOne($sql);
if ($currentLevel !== null) {
$this->nextValue = $currentLevel;
$this->maxValue = $this->nextValue + $this->allocationSize;
$updateSql = $conn->getDatabasePlatform()->getTableHiLoUpdateNextValSql($this->tableName, $this->sequenceName, $this->allocationSize);
if ($conn->executeStatement($updateSql, [1 => $currentLevel, 2 => $currentLevel + 1]) !== 1) {
}
} else {
}
} else {
}
}
return $this->nextValue++;
}
}
