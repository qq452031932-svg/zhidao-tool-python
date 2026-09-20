# M18 命令行与编排

公开 `main(argv)` 提供 mine/collect/transfer/template/publish/answer/run 七命令；每一步独立调用既有模块。全流程固定把关键词、采集资源表、转存资源表、问答表写到工作目录后才继续。`run` 接受简单的嵌套 YAML 映射（及 JSON）；避免为配置引入新依赖。external 模式将采集表写入 C# inbox，等待 outbox 中同名结果再通过 M02 读写成内部三列表。凭据使用 M01 ConfigStore，不写进流水线文件。

先以假采集器、假网盘客户端与假发布接口验证独立命令和编排；真实账号联调需要用户本机配置，离线测试不宣称线上可用。
