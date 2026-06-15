# Python编程完全指南

## 一、Python基础

### 1.1 变量和数据类型

Python支持多种数据类型：
- 整数(int)：x = 10
- 浮点数(float)：y = 3.14
- 字符串(str)：name = "Python"
- 布尔(bool)：is_valid = True
- 列表(list)：fruits = ["apple", "banana", "cherry"]
- 元组(tuple)：point = (10, 20)
- 字典(dict)：person = {"name": "Alice", "age": 30}
- 集合(set)：unique = {1, 2, 3}

### 1.2 控制流

条件语句：if-elif-else
循环：for循环、while循环
列表推导式：squares = [x**2 for x in range(10)]

### 1.3 函数

定义函数使用def关键字，支持默认参数、可变参数(*args)、关键字参数(**kwargs)。
Lambda函数：square = lambda x: x**2

### 1.4 面向对象编程

类定义：class Dog: def __init__(self, name): ...
继承：class Puppy(Dog): ...
封装、继承、多态是OOP三大特性。

## 二、Python进阶

### 2.1 装饰器

装饰器是修改函数行为的高阶函数。使用@语法糖。
常见装饰器：@property, @staticmethod, @classmethod, @functools.lru_cache

### 2.2 生成器

生成器使用yield关键字，惰性计算，节省内存。
生成器表达式：gen = (x**2 for x in range(10))

### 2.3 上下文管理器

with语句自动管理资源。自定义上下文管理器需要实现__enter__和__exit__方法。

### 2.4 异步编程

asyncio模块支持异步IO。async/await语法。
适合IO密集型任务：网络请求、文件操作。

## 三、标准库

os模块：文件和目录操作
sys模块：系统相关参数
json模块：JSON序列化和反序列化
datetime模块：日期时间处理
collections模块：高级数据结构(defaultdict, Counter, deque)
re模块：正则表达式
itertools模块：迭代器工具
functools模块：函数工具

## 四、Web开发

### 4.1 Flask

轻量级Web框架，适合小型项目和API。
路由@app.route()，模板Jinja2，扩展丰富。

### 4.2 FastAPI

现代高性能Web框架，基于类型提示自动生成API文档。
支持异步，性能接近Node.js和Go。
Pydantic数据验证，OpenAPI文档自动生成。

### 4.3 Django

全功能Web框架，包含ORM、模板、管理后台。
适合大型项目，"batteries included"理念。

## 五、数据科学

NumPy：多维数组和数学运算
Pandas：数据分析和处理(DataFrame)
Matplotlib/Seaborn：数据可视化
Scikit-learn：机器学习库

## 六、最佳实践

虚拟环境：python -m venv myenv
类型提示：def greet(name: str) -> str
代码格式化：black, isort
类型检查：mypy
测试：unittest, pytest
日志：logging模块

## 七、并发编程

多线程threading：适合IO密集型
多进程multiprocessing：适合CPU密集型
异步IO asyncio：适合高并发IO
concurrent.futures：线程池和进程池

## 八、包管理

pip install package_name
pip freeze > requirements.txt
pip install -r requirements.txt
poetry现代包管理工具
pyproject.toml项目配置

## 九、项目结构

标准结构：src/、tests/、docs/、README.md、requirements.txt、setup.py
打包发布：setuptools、poetry build

## 十、高级特性

元编程：元类(metaclass)
描述符：自定义属性访问
协程：yield和send
C扩展：ctypes、Cython
