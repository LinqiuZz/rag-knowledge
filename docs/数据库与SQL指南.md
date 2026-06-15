# 数据库与SQL完全指南

## 一、关系型数据库原理

### 1.1 什么是关系型数据库

关系型数据库基于关系模型，数据以表(Table)的形式组织。每个表由行(Row)和列(Column)组成。

核心概念：
- 关系(Relation)：即表
- 元组(Tuple)：即行
- 属性(Attribute)：即列
- 主键(Primary Key)：唯一标识一行
- 外键(Foreign Key)：建立表间关系

### 1.2 数据库设计范式

第一范式(1NF)：属性不可再分(原子性)
第二范式(2NF)：非主属性完全依赖于主键
第三范式(3NF)：非主属性不传递依赖于主键
BC范式(BCNF)：所有决定因素都是候选键

### 1.3 ER模型

实体(Entity)：现实世界的对象
属性(Attribute)：实体的特征
关系(Relationship)：实体间的联系(1:1, 1:N, M:N)

## 二、SQL语法

### 2.1 DDL(数据定义语言)

创建表：
CREATE TABLE users (
    id INT PRIMARY KEY AUTO_INCREMENT,
    username VARCHAR(50) NOT NULL UNIQUE,
    email VARCHAR(100),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

修改表：
ALTER TABLE users ADD COLUMN age INT;
ALTER TABLE users DROP COLUMN age;
ALTER TABLE users MODIFY COLUMN email VARCHAR(200);

删除表：DROP TABLE users;
截断表：TRUNCATE TABLE users;

### 2.2 DML(数据操作语言)

插入数据：
INSERT INTO users (username, email) VALUES ('alice', 'alice@example.com');
INSERT INTO users VALUES (1, 'bob', 'bob@example.com', NOW());

更新数据：
UPDATE users SET email = 'new@example.com' WHERE id = 1;

删除数据：
DELETE FROM users WHERE id = 1;

### 2.3 DQL(数据查询语言)

基本查询：
SELECT * FROM users;
SELECT username, email FROM users;

条件查询：
SELECT * FROM users WHERE age > 18;
SELECT * FROM users WHERE username LIKE 'a%';
SELECT * FROM users WHERE id IN (1, 2, 3);

排序：
SELECT * FROM users ORDER BY created_at DESC;
SELECT * FROM users ORDER BY age ASC, username DESC;

分页：
SELECT * FROM users LIMIT 10 OFFSET 20;
SELECT * FROM users LIMIT 20, 10;

聚合函数：
SELECT COUNT(*) FROM users;
SELECT AVG(age) FROM users;
SELECT MAX(age), MIN(age) FROM users;
SELECT SUM(salary) FROM employees;

分组：
SELECT department, COUNT(*) FROM employees GROUP BY department;
SELECT department, AVG(salary) FROM employees GROUP BY department HAVING AVG(salary) > 5000;

### 2.4 连接查询

内连接(INNER JOIN)：
SELECT u.username, o.order_id
FROM users u INNER JOIN orders o ON u.id = o.user_id;

左连接(LEFT JOIN)：
SELECT u.username, o.order_id
FROM users u LEFT JOIN orders o ON u.id = o.user_id;

右连接(RIGHT JOIN)：
SELECT u.username, o.order_id
FROM users u RIGHT JOIN orders o ON u.id = o.user_id;

全连接(FULL JOIN)：MySQL不支持，可用UNION模拟

自连接：
SELECT e.name, m.name AS manager
FROM employees e JOIN employees m ON e.manager_id = m.id;

### 2.5 子查询

WHERE子查询：
SELECT * FROM users WHERE id IN (SELECT user_id FROM orders);

FROM子查询：
SELECT * FROM (SELECT department, AVG(salary) AS avg_sal FROM employees GROUP BY department) t WHERE avg_sal > 5000;

EXISTS子查询：
SELECT * FROM users u WHERE EXISTS (SELECT 1 FROM orders o WHERE o.user_id = u.id);

### 2.6 窗口函数

ROW_NUMBER()：行号
RANK()：排名(可并列)
DENSE_RANK()：密集排名
LAG()/LEAD()：前/后N行的值
SUM() OVER()：累计求和

示例：
SELECT name, department, salary,
    RANK() OVER(PARTITION BY department ORDER BY salary DESC) AS rank
FROM employees;

## 三、索引原理

### 3.1 B+树索引

B+树是MySQL InnoDB默认的索引结构。

特点：
- 所有数据存储在叶子节点
- 叶子节点通过链表连接
- 非叶子节点只存储索引
- 树高度通常3-4层

### 3.2 索引类型

主键索引：PRIMARY KEY
唯一索引：UNIQUE INDEX
普通索引：INDEX
组合索引：INDEX(col1, col2)
全文索引：FULLTEXT INDEX

### 3.3 索引优化

最左前缀原则：组合索引(a,b,c)可以使用a、(a,b)、(a,b,c)
覆盖索引：查询的列都在索引中
索引下推(ICP)：在存储引擎层过滤
避免索引失效：函数操作、隐式转换、LIKE '%xxx'

## 四、事务与锁

### 4.1 ACID特性

原子性(Atomicity)：事务要么全部成功，要么全部回滚
一致性(Consistency)：事务前后数据保持一致
隔离性(Isolation)：并发事务互不干扰
持久性(Durability)：事务提交后永久保存

### 4.2 隔离级别

READ UNCOMMITTED：读未提交(脏读)
READ COMMITTED：读已提交(不可重复读)
REPEATABLE READ：可重复读(MySQL默认)
SERIALIZABLE：串行化(最安全但最慢)

### 4.3 锁机制

表锁：锁定整张表
行锁：锁定单行(InnoDB)
间隙锁(Gap Lock)：锁定范围
临键锁(Next-Key Lock)：行锁+间隙锁

死锁处理：等待超时、死锁检测、回滚代价小的事务

## 五、MySQL优化

### 5.1 查询优化

EXPLAIN分析查询计划
避免SELECT *，只查需要的列
合理使用索引
避免在WHERE中使用函数
使用LIMIT限制结果集

### 5.2 表结构优化

选择合适的数据类型
使用NOT NULL约束
合理使用范式和反范式
大表分区(Partition)

### 5.3 配置优化

innodb_buffer_pool_size：缓冲池大小
innodb_log_file_size：日志文件大小
max_connections：最大连接数
query_cache_type：查询缓存

## 六、NoSQL

### 6.1 Redis

内存键值存储，支持多种数据结构。

数据类型：String, List, Set, Hash, ZSet, HyperLogLog, Stream, Bitmap
持久化：RDB快照、AOF日志
应用场景：缓存、会话、排行榜、计数器、消息队列

### 6.2 MongoDB

文档型数据库，JSON格式存储。

核心概念：Database、Collection、Document
查询：find(), aggregate()
索引：单字段、复合、文本、地理空间
应用场景：内容管理、日志、用户档案

### 6.3 选型建议

关系型(MySQL)：强一致性、复杂查询、事务
Redis：缓存、会话、实时数据
MongoDB：灵活Schema、文档存储
Elasticsearch：全文搜索、日志分析

## 七、数据安全

SQL注入防护：参数化查询、ORM
权限控制：GRANT/REVOKE
数据加密：传输加密(SSL)、存储加密
备份策略：全量备份、增量备份、binlog

## 八、数据库设计实践

需求分析 -> 概念设计(ER图) -> 逻辑设计(表结构) -> 物理设计(索引、分区)
命名规范：表名复数、字段下划线、避免保留字
文档化：维护数据字典
