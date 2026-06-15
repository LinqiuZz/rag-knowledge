# Java编程完全指南

## 一、Java基础

### 1.1 数据类型

基本类型：byte, short, int, long, float, double, char, boolean
引用类型：类、接口、数组

### 1.2 面向对象

类和对象
封装：private + getter/setter
继承：extends
多态：方法重写、向上转型
抽象类：abstract class
接口：interface

### 1.3 集合框架

List：ArrayList(数组)、LinkedList(链表)
Set：HashSet(哈希)、TreeSet(红黑树)
Map：HashMap、TreeMap、ConcurrentHashMap
Queue：LinkedList、PriorityQueue

### 1.4 异常处理

try-catch-finally
throws声明异常
自定义异常
try-with-resources

## 二、Java进阶

### 2.1 泛型

泛型类：class Box<T> { T value; }
泛型方法：<T> T method(T t)
通配符：? extends T, ? super T
类型擦除

### 2.2 注解

内置注解：@Override, @Deprecated, @SuppressWarnings
元注解：@Target, @Retention
自定义注解

### 2.3 反射

Class对象
获取构造器、方法、字段
动态代理

### 2.4 IO/NIO

字节流/字符流
缓冲流
NIO：Channel、Buffer、Selector
AIO：异步IO

## 三、多线程与并发

### 3.1 线程基础

创建线程：继承Thread、实现Runnable、实现Callable
线程状态：NEW, RUNNABLE, BLOCKED, WAITING, TIMED_WAITING, TERMINATED
线程安全：synchronized, volatile, Atomic类

### 3.2 并发工具

Lock：ReentrantLock, ReadWriteLock
并发集合：ConcurrentHashMap, CopyOnWriteArrayList
线程池：ThreadPoolExecutor, Executors
并发工具：CountDownLatch, CyclicBarrier, Semaphore
CompletableFuture：异步编程

### 3.3 JMM(Java内存模型)

主内存与工作内存
happens-before原则
volatile语义

## 四、JVM

### 4.1 内存模型

堆(Heap)：对象存储
栈(Stack)：方法调用
方法区(Method Area)：类信息、常量
程序计数器

### 4.2 垃圾回收

GC算法：标记-清除、标记-整理、复制算法
分代收集：新生代(Eden, S0, S1)、老年代
GC收集器：Serial, Parallel, CMS, G1, ZGC
调优参数：-Xms, -Xmx, -XX:NewRatio

### 4.3 类加载

加载 -> 验证 -> 准备 -> 解析 -> 初始化
双亲委派模型
自定义类加载器

## 五、Spring框架

### 5.1 Spring Core

IoC容器：管理Bean的生命周期
DI(依赖注入)：构造器注入、字段注入、Setter注入
AOP(面向切面编程)：@Aspect, @Before, @After

### 5.2 Spring Boot

自动配置：@EnableAutoConfiguration
起步依赖：starter
内嵌Tomcat
配置文件：application.yml

### 5.3 Spring MVC

@Controller / @RestController
@RequestMapping
@RequestParam, @PathVariable, @RequestBody
返回值处理：JSON、视图

### 5.4 Spring Data JPA

@Entity, @Table, @Column
Repository接口
JPQL查询
分页排序

### 5.5 Spring Security

认证和授权
JWT Token
OAuth2
CSRF防护

## 六、MyBatis

### 6.1 基本使用

Mapper接口
XML映射文件
动态SQL：if, choose, foreach

### 6.2 MyBatis-Plus

CRUD接口
条件构造器
分页插件
代码生成器

## 七、微服务

### 7.1 Spring Cloud

服务注册：Eureka, Nacos
服务调用：Feign, RestTemplate
网关：Gateway, Zuul
配置中心：Config, Nacos
熔断：Hystrix, Sentinel

### 7.2 Dubbo

RPC框架
服务提供者/消费者
负载均衡
集群容错

## 八、工具与实践

构建工具：Maven, Gradle
IDE：IntelliJ IDEA
单元测试：JUnit, Mockito
代码规范：Alibaba Java Coding Guidelines
日志：SLF4J + Logback
