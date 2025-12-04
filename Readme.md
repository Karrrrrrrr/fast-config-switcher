

本项目用来快速切换consul配置文件

解决以下痛点

项目中含有较多微服务，并且有大量类似的配置，比如有多个服务都连同一个数据库，这种情况下如果要切换数据库，需要手动修改所有配置
或者是提前准备不同的consul-key来切换

准备不同的consul-key 随着开发 会有部分配置是不同步的，此时还是需要手动去同步，非常麻烦

本项目的方案如下

比如运行如下命令
读取当前目录中develop.yml作为变量文件
如果不存在就退而求其次读取 ```~/.config/consul/develop.yml```
还不存在就结束程序

然后去递归扫描 ./config/**.yml
如果存在，就会把文件名去掉后缀作为consul-key，把里面的变量替换为变量文件中定义的值

```shell
python3 switch.py -env develop
```
比如有
```config/kratos/template.yml```

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

```varable/develop.yml```

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