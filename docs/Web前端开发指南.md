# Web前端开发指南

## 一、HTML5基础

### 1.1 语义化标签

header：页头
nav：导航
main：主要内容
article：文章
section：节
aside：侧边栏
footer：页脚

### 1.2 表单元素

input类型：text, email, password, number, date, file, range
表单验证：required, pattern, min/max
新特性：datalist, output, progress, meter

### 1.3 多媒体

audio：音频播放
video：视频播放
canvas：2D绘图
SVG：矢量图形

## 二、CSS3

### 2.1 选择器

基础选择器：元素、类、ID、属性
组合选择器：后代、子元素、相邻兄弟
伪类：:hover, :focus, :nth-child
伪元素：::before, ::after

### 2.2 布局

Flexbox布局：
- display: flex
- justify-content: 主轴对齐
- align-items: 交叉轴对齐
- flex-wrap: 换行

Grid布局：
- display: grid
- grid-template-columns/rows
- grid-gap: 间距
- grid-area: 区域

### 2.3 响应式设计

媒体查询：@media (max-width: 768px) { ... }
移动优先：先写移动端样式
断点：常用768px、1024px、1200px
单位：rem、em、vw、vh

### 2.4 动画

transition：过渡动画
transform：2D/3D变换
@keyframes：关键帧动画
animation：动画属性

## 三、JavaScript基础

### 3.1 数据类型

原始类型：string, number, boolean, null, undefined, symbol, bigint
引用类型：object, array, function

### 3.2 函数

函数声明：function foo() { ... }
函数表达式：const foo = function() { ... }
箭头函数：const foo = () => { ... }
闭包：函数记住外部作用域

### 3.3 ES6+特性

let/const：块级作用域
模板字符串：`Hello ${name}`
解构赋值：const {a, b} = obj
展开运算符：...arr
Promise：异步处理
async/await：异步语法糖

### 3.4 DOM操作

获取元素：querySelector, getElementById
事件处理：addEventListener
创建元素：createElement
修改样式：style, classList

## 四、Vue3

### 4.1 Composition API

setup()函数
ref：基本类型响应式
reactive：对象响应式
computed：计算属性
watch/watchEffect：侦听器

### 4.2 组件

组件定义和注册
Props和Emits
插槽(Slot)
provide/inject

### 4.3 Vue Router

路由配置
动态路由：/user/:id
导航守卫
嵌套路由

### 4.4 Pinia状态管理

defineStore
state, getters, actions
持久化存储

## 五、TypeScript

### 5.1 基础类型

string, number, boolean
array: number[]
tuple: [string, number]
enum
any, unknown, void, never

### 5.2 接口和类型

interface：对象形状
type：类型别名
泛型：Array<T>
联合类型：string | number

### 5.3 类

类定义和继承
访问修饰符：public, private, protected
抽象类
接口实现

## 六、前端工程化

### 6.1 Vite

快速开发服务器
ES Module原生支持
热模块替换(HMR)
构建优化

### 6.2 Webpack

模块打包
Loader：转换文件
Plugin：扩展功能
代码分割

### 6.3 ESLint和Prettier

代码规范检查
自动格式化
编辑器集成

## 七、性能优化

### 7.1 加载优化

代码分割(Code Splitting)
懒加载(Lazy Loading)
预加载(Preload)
CDN加速

### 7.2 渲染优化

虚拟滚动
requestAnimationFrame
避免重排(Reflow)
CSS will-change

### 7.3 网络优化

HTTP缓存
Service Worker
资源压缩
图片优化(WebP)

## 八、测试

单元测试：Vitest, Jest
组件测试：Vue Test Utils
E2E测试：Cypress, Playwright

## 九、部署

构建：npm run build
静态托管：Vercel, Netlify, GitHub Pages
容器化：Docker + Nginx
CI/CD：GitHub Actions

## 十、工具链

包管理：npm, yarn, pnpm
版本控制：Git
编辑器：VS Code
浏览器DevTools
