# DB 设计

不想引入复杂的DB系统，Alfred中也只有有极少情况并发写，所以使用SQLite3作为数据库，将写加锁，确保线程安全。
读操作不加锁，允许并发读。

## Bulletin

详细表结构见 `init.sql` 。

作为“公告板”，存储TODO模板、TODO以及TODO Log。

TaskEngine和Slack

