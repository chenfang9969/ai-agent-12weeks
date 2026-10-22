# 文章翻译审校 · 状态图（W02 交付物）

> 由 `python translate_graph.py --draw` 生成。
> 实现文件：`../translate_graph.py`

## 状态图

```mermaid
flowchart TD
    translate["translate"]
    review["review"]
    publish["publish"]
    translate --> review
    publish --> DONE([结束])
    review {条件边 router}
    review -->|通过/超过上限| publish
    review -->|打回重译| translate
```

## 三个概念对应的代码位置

| 概念 | 在这张图里 | 代码位置 |
|---|---|---|
| **State** | 在节点之间流动的那份数据 | `new_state()`：5 个字段 |
| **Node** | translate / review / publish | 三个 `node_*` 函数 |
| **Edge** | `translate → review` 固定边 | `add_edge("translate", "review")` |
| **条件边** | review 之后的分岔 | `route_review()` 返回节点名 |

## 状态字段

| 字段 | 类型 | 作用 |
|---|---|---|
| `source_text` | str | 中文原文，全程不变 |
| `translation` | str | 当前译文，每轮覆盖 |
| `approved` | bool | 审核是否通过 |
| `round` | int | 第几稿（translate 里 +1）|
| `review_feedback` | str | 审核意见，喂给下一轮翻译 |

---

## 我写的说明（这一节必须本人写，不许抄）

### 这个图和 `workflow.py` 里"研究助手"的图，哪里一样？

答：流程是相同的，并且相关的节点间的关系和位置是一样的

### 哪里不一样？

答：这个是由本身配置的文件来完成的，而研究助手是能够通过工具去进行调用来抓取网络节点的，比研究助手少了网络知识获取节点

### 我以为会很难、结果很简单的一件事

答：完成LLM中的函数的配置和相关文件操作的参数，还有就是实现 的逻辑

---

## 实测记录

| 场景 | 结果 |
|---|---|
| `--mock --auto` | 1 轮结束，落盘"已通过" |
| `--mock` + 连按 3 次 n | 循环 3 轮后强制定稿，落盘带"未通过审核"+最后意见 |
| `--auto`（真 LLM） | 输出真英文 |
| 真 LLM + 打回一次（意见：太生硬，用更自然的英文） | 第 2 稿措辞确实变了 |

**最后一行的意义**：`review_feedback` 这个字段不是摆设——它真的会影响模型输出。
