
### 初始化

```shell
pip install py-consul pyyaml
```

### 项目来源
本项目用来快速切换consul配置文件

解决以下痛点

当项目中含有较多微服务，并且有大量类似的配置，比如有多个服务都连同一个数据库，这种情况下如果要切换数据库(比如本地数据库要切换到测试服数据库，或者当切换分支的时候，要切换一个干净的数据库用于调试），
需要手动修改所有配置，并且手动修改还有改错 漏改的可能性


本项目的方案及工作原理如下

当运行本程序 ```python switch.py -env develop```
读取当前目录中```./variable/develop.yml```作为变量文件
如果不存在就退而求其次读取 ```~/.config/consul/variable/develop.yml```
还不存在就结束程序

然后去递归扫描 ./templates/**.yml
如果存在，就会把文件名去掉后缀作为consul-key，把里面的变量替换为变量文件中定义的值
 
比如有
```templates/kratos/template.yml```

```yaml
# 这里配置服务固定的参数
http:
  port: 8000

# 使用变量配置比较通用的参数
db:
  host: ${mysql.host}
  port: ${mysql.port}
  dbname: ${mysql.dbname}
redis:
  host: ${redis.host}
  port: ${redis.port}
  db: ${redis.db}

```

```variable/develop.yml```

```yaml

mysql.host: mysql
mysql.port: 3306
mysql.dbname: kratos

redis.port: 6379
redis.host: "redis"
redis.db: 0

```

运行之后， 就会把直接替换为 
```shell
# 这里配置服务固定的参数
http:
  port: 8000

# 使用变量配置比较通用的参数
db:
  host: "mysql"
  port: 3306
  dbname: "kratos"
redis:
  host: "redis"
  port: 6379
  db: 0

```

然后写入到consul的 ```kratos/template ```


### 建议
把这个文件放到环境变量可找到的地方，bash中配置一下顺手的alias