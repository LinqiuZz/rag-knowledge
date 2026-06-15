"""
机器学习常用算法实现示例
========================
本文件展示了机器学习中常见算法的 Python 实现，包括：
- 线性回归（梯度下降法）
- K-Means 聚类
- KNN 分类器
- 朴素贝叶斯分类器
- 决策树（ID3）
"""

import numpy as np
from collections import Counter
from typing import List, Tuple, Optional


# ──────────────────────────────────────────────
# 1. 线性回归（梯度下降法）
# ──────────────────────────────────────────────

class LinearRegression:
    """使用梯度下降法实现的线性回归。
    
    损失函数: MSE = (1/2n) * Σ(y_pred - y_true)^2
    
    参数:
        learning_rate: 学习率，控制步长大小
        n_iterations: 迭代次数
        regularization: L2 正则化系数（Ridge）
    """
    
    def __init__(self, learning_rate=0.01, n_iterations=1000, regularization=0.0):
        self.lr = learning_rate
        self.n_iter = n_iterations
        self.reg = regularization
        self.weights = None
        self.bias = None
        self.losses = []
    
    def fit(self, X: np.ndarray, y: np.ndarray):
        """训练模型。"""
        n_samples, n_features = X.shape
        self.weights = np.zeros(n_features)
        self.bias = 0
        self.losses = []
        
        for i in range(self.n_iter):
            # 前向传播
            y_pred = np.dot(X, self.weights) + self.bias
            
            # 计算损失
            loss = np.mean((y_pred - y) ** 2) / 2
            reg_loss = self.reg * np.sum(self.weights ** 2) / (2 * n_samples)
            self.losses.append(loss + reg_loss)
            
            # 计算梯度
            dw = (1 / n_samples) * np.dot(X.T, (y_pred - y)) + self.reg * self.weights / n_samples
            db = (1 / n_samples) * np.sum(y_pred - y)
            
            # 更新参数
            self.weights -= self.lr * dw
            self.bias -= self.lr * db
    
    def predict(self, X: np.ndarray) -> np.ndarray:
        """预测。"""
        return np.dot(X, self.weights) + self.bias


# ──────────────────────────────────────────────
# 2. K-Means 聚类
# ──────────────────────────────────────────────

class KMeans:
    """K-Means 聚类算法。
    
    算法步骤:
    1. 随机选择 K 个初始质心
    2. 将每个样本分配到最近的质心
    3. 重新计算每个簇的质心
    4. 重复步骤 2-3 直到收敛
    
    参数:
        n_clusters: 聚类数量 K
        max_iter: 最大迭代次数
        tol: 收敛阈值
    """
    
    def __init__(self, n_clusters=3, max_iter=100, tol=1e-4):
        self.k = n_clusters
        self.max_iter = max_iter
        self.tol = tol
        self.centroids = None
        self.labels = None
        self.inertia_ = None  # 簇内平方和
    
    def fit(self, X: np.ndarray):
        """训练聚类模型。"""
        n_samples, n_features = X.shape
        
        # 随机初始化质心
        idx = np.random.choice(n_samples, self.k, replace=False)
        self.centroids = X[idx].copy()
        
        for iteration in range(self.max_iter):
            old_centroids = self.centroids.copy()
            
            # 计算每个样本到各质心的距离
            distances = np.zeros((n_samples, self.k))
            for i in range(self.k):
                distances[:, i] = np.linalg.norm(X - self.centroids[i], axis=1)
            
            # 分配到最近的质心
            self.labels = np.argmin(distances, axis=1)
            
            # 更新质心
            for i in range(self.k):
                cluster_points = X[self.labels == i]
                if len(cluster_points) > 0:
                    self.centroids[i] = cluster_points.mean(axis=0)
            
            # 检查收敛
            shift = np.linalg.norm(self.centroids - old_centroids)
            if shift < self.tol:
                print(f"K-Means 在第 {iteration+1} 轮收敛")
                break
        
        # 计算惯性（簇内平方和）
        self.inertia_ = 0
        for i in range(self.k):
            cluster_points = X[self.labels == i]
            self.inertia_ += np.sum((cluster_points - self.centroids[i]) ** 2)
        
        return self
    
    def predict(self, X: np.ndarray) -> np.ndarray:
        """预测新样本的簇标签。"""
        distances = np.zeros((len(X), self.k))
        for i in range(self.k):
            distances[:, i] = np.linalg.norm(X - self.centroids[i], axis=1)
        return np.argmin(distances, axis=1)


# ──────────────────────────────────────────────
# 3. KNN 分类器
# ──────────────────────────────────────────────

class KNN:
    """K 近邻分类器。
    
    算法原理:
    1. 计算待分类样本与所有训练样本的距离
    2. 选择距离最近的 K 个样本
    3. 通过投票决定类别
    
    距离度量:
    - euclidean: 欧氏距离 √(Σ(a-b)^2)
    - manhattan: 曼哈顿距离 Σ|a-b|
    """
    
    def __init__(self, k=3, metric='euclidean'):
        self.k = k
        self.metric = metric
        self.X_train = None
        self.y_train = None
    
    def fit(self, X: np.ndarray, y: np.ndarray):
        """存储训练数据（KNN 是惰性学习算法）。"""
        self.X_train = X
        self.y_train = y
    
    def _distance(self, a: np.ndarray, b: np.ndarray) -> float:
        """计算两个样本之间的距离。"""
        if self.metric == 'euclidean':
            return np.sqrt(np.sum((a - b) ** 2))
        elif self.metric == 'manhattan':
            return np.sum(np.abs(a - b))
        else:
            raise ValueError(f"未知距离度量: {self.metric}")
    
    def predict(self, X: np.ndarray) -> np.ndarray:
        """预测类别。"""
        predictions = []
        for x in X:
            # 计算与所有训练样本的距离
            distances = [self._distance(x, x_train) for x_train in self.X_train]
            # 选择最近的 K 个样本的索引
            k_indices = np.argsort(distances)[:self.k]
            # 获取这些样本的标签
            k_labels = self.y_train[k_indices]
            # 投票决定类别
            most_common = Counter(k_labels).most_common(1)[0][0]
            predictions.append(most_common)
        return np.array(predictions)


# ──────────────────────────────────────────────
# 4. 朴素贝叶斯分类器
# ──────────────────────────────────────────────

class NaiveBayes:
    """高斯朴素贝叶斯分类器。
    
    基于贝叶斯定理: P(y|X) = P(X|y) * P(y) / P(X)
    
    朴素假设: 特征之间条件独立
    P(X|y) = Π P(xi|y)
    
    对于连续特征，假设服从高斯分布:
    P(xi|y) = (1/√(2πσ²)) * exp(-(xi-μ)²/(2σ²))
    """
    
    def fit(self, X: np.ndarray, y: np.ndarray):
        """计算每个类别的均值、方差和先验概率。"""
        self.classes = np.unique(y)
        self.n_classes = len(self.classes)
        n_features = X.shape[1]
        
        self.mean = np.zeros((self.n_classes, n_features))
        self.var = np.zeros((self.n_classes, n_features))
        self.prior = np.zeros(self.n_classes)
        
        for i, c in enumerate(self.classes):
            X_c = X[y == c]
            self.mean[i] = X_c.mean(axis=0)
            self.var[i] = X_c.var(axis=0) + 1e-9  # 防止除零
            self.prior[i] = len(X_c) / len(X)
    
    def _gaussian_pdf(self, x: np.ndarray, mean: np.ndarray, var: np.ndarray) -> np.ndarray:
        """计算高斯概率密度。"""
        coeff = 1 / np.sqrt(2 * np.pi * var)
        exponent = np.exp(-((x - mean) ** 2) / (2 * var))
        return coeff * exponent
    
    def predict(self, X: np.ndarray) -> np.ndarray:
        """预测类别。"""
        predictions = []
        for x in X:
            posteriors = []
            for i in range(self.n_classes):
                # 计算对数后验概率（避免下溢）
                log_prior = np.log(self.prior[i])
                log_likelihood = np.sum(np.log(self._gaussian_pdf(x, self.mean[i], self.var[i])))
                posteriors.append(log_prior + log_likelihood)
            predictions.append(self.classes[np.argmax(posteriors)])
        return np.array(predictions)


# ──────────────────────────────────────────────
# 5. 决策树（ID3 算法）
# ──────────────────────────────────────────────

class DecisionTree:
    """ID3 决策树分类器。
    
    使用信息增益作为分裂准则:
    - 信息熵: H(S) = -Σ p*log2(p)
    - 信息增益: IG = H(S) - Σ (|Sv|/|S|)*H(Sv)
    
    参数:
        max_depth: 最大深度（防止过拟合）
        min_samples_split: 最小分裂样本数
    """
    
    def __init__(self, max_depth=10, min_samples_split=2):
        self.max_depth = max_depth
        self.min_samples_split = min_samples_split
        self.tree = None
    
    def _entropy(self, y: np.ndarray) -> float:
        """计算信息熵。"""
        _, counts = np.unique(y, return_counts=True)
        probs = counts / len(y)
        return -np.sum(probs * np.log2(probs + 1e-9))
    
    def _best_split(self, X: np.ndarray, y: np.ndarray) -> Tuple[int, float]:
        """找到最佳分裂特征和阈值。"""
        best_gain = -1
        best_feature = None
        best_threshold = None
        current_entropy = self._entropy(y)
        
        for feature in range(X.shape[1]):
            thresholds = np.unique(X[:, feature])
            for threshold in thresholds:
                left_mask = X[:, feature] <= threshold
                right_mask = ~left_mask
                
                if np.sum(left_mask) == 0 or np.sum(right_mask) == 0:
                    continue
                
                # 计算信息增益
                left_entropy = self._entropy(y[left_mask])
                right_entropy = self._entropy(y[right_mask])
                n = len(y)
                gain = current_entropy - (np.sum(left_mask)/n * left_entropy + np.sum(right_mask)/n * right_entropy)
                
                if gain > best_gain:
                    best_gain = gain
                    best_feature = feature
                    best_threshold = threshold
        
        return best_feature, best_threshold
    
    def _build_tree(self, X: np.ndarray, y: np.ndarray, depth: int) -> dict:
        """递归构建决策树。"""
        # 终止条件
        if (depth >= self.max_depth or 
            len(np.unique(y)) == 1 or 
            len(y) < self.min_samples_split):
            return {'leaf': True, 'class': Counter(y).most_common(1)[0][0]}
        
        feature, threshold = self._best_split(X, y)
        if feature is None:
            return {'leaf': True, 'class': Counter(y).most_common(1)[0][0]}
        
        left_mask = X[:, feature] <= threshold
        return {
            'leaf': False,
            'feature': feature,
            'threshold': threshold,
            'left': self._build_tree(X[left_mask], y[left_mask], depth + 1),
            'right': self._build_tree(X[~left_mask], y[~left_mask], depth + 1),
        }
    
    def fit(self, X: np.ndarray, y: np.ndarray):
        """构建决策树。"""
        self.tree = self._build_tree(X, y, 0)
    
    def _predict_one(self, x: np.ndarray, node: dict) -> int:
        """预测单个样本。"""
        if node['leaf']:
            return node['class']
        if x[node['feature']] <= node['threshold']:
            return self._predict_one(x, node['left'])
        return self._predict_one(x, node['right'])
    
    def predict(self, X: np.ndarray) -> np.ndarray:
        """预测类别。"""
        return np.array([self._predict_one(x, self.tree) for x in X])


# ──────────────────────────────────────────────
# 使用示例
# ──────────────────────────────────────────────

if __name__ == "__main__":
    # 生成示例数据
    np.random.seed(42)
    X_train = np.vstack([
        np.random.randn(50, 2) + [2, 2],
        np.random.randn(50, 2) + [-2, -2],
        np.random.randn(50, 2) + [2, -2],
    ])
    y_train = np.array([0]*50 + [1]*50 + [2]*50)
    
    # 测试 KNN
    knn = KNN(k=5)
    knn.fit(X_train, y_train)
    predictions = knn.predict(X_train[:5])
    print(f"KNN 预测: {predictions}")
    
    # 测试 K-Means
    kmeans = KMeans(n_clusters=3)
    kmeans.fit(X_train)
    print(f"K-Means 惯性: {kmeans.inertia_:.2f}")
    
    # 测试朴素贝叶斯
    nb = NaiveBayes()
    nb.fit(X_train, y_train)
    predictions = nb.predict(X_train[:5])
    print(f"朴素贝叶斯预测: {predictions}")
